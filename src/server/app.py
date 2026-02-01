import os
import yaml
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Setup logging
logger = logging.getLogger("mae_server")

app = FastAPI(title="MAE Management Server")

# Constants
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config" / "agents"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Models
class AgentConfig(BaseModel):
    name: str
    config_content: str

class DryRunRequest(BaseModel):
    target_labels: Optional[str] = None

class AuthCodeRequest(BaseModel):
    code: str

# --- API Endpoints ---

@app.get("/api/agents")
async def list_agents():
    """List all available agents"""
    agents = []
    if CONFIG_DIR.exists():
        for config_file in CONFIG_DIR.glob("*.yaml"):
            if config_file.name.endswith(".example"):
                continue
            
            # Basic parsing to get status (enabled/disabled)
            try:
                with open(config_file, "r") as f:
                    content = yaml.safe_load(f)
                    enabled = content.get("agent", {}).get("enabled", False)
                    agents.append({
                        "name": config_file.stem,
                        "enabled": enabled,
                        "filename": config_file.name
                    })
            except Exception as e:
                logger.error(f"Error reading {config_file}: {e}")
                agents.append({
                    "name": config_file.stem,
                    "enabled": False,
                    "error": str(e),
                    "filename": config_file.name
                })
    return agents

@app.get("/api/agents/{agent_name}")
async def get_agent_config(agent_name: str):
    """Get raw configuration for an agent"""
    config_file = CONFIG_DIR / f"{agent_name}.yaml"
    if not config_file.exists():
        raise HTTPException(status_code=404, detail="Agent not found")
    
    with open(config_file, "r") as f:
        content = f.read()
    
    return {"name": agent_name, "config_content": content}

@app.post("/api/agents/{agent_name}")
async def update_agent_config(agent_name: str, config: AgentConfig):
    """Update configuration for an agent"""
    config_file = CONFIG_DIR / f"{agent_name}.yaml"
    
    # Validate YAML
    try:
        yaml.safe_load(config.config_content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    
    with open(config_file, "w") as f:
        f.write(config.config_content)
    
    return {"status": "updated", "name": agent_name}

@app.post("/api/agents")
async def create_agent(config: AgentConfig):
    """Create a new agent"""
    if not config.name:
        raise HTTPException(status_code=400, detail="Agent name is required")
    
    config_file = CONFIG_DIR / f"{config.name}.yaml"
    if config_file.exists():
        raise HTTPException(status_code=400, detail="Agent already exists")
    
    # Validate YAML
    try:
        yaml.safe_load(config.config_content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    
    with open(config_file, "w") as f:
        f.write(config.config_content)
    
    return {"status": "created", "name": config.name}

@app.delete("/api/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """Delete an agent"""
    config_file = CONFIG_DIR / f"{agent_name}.yaml"
    if not config_file.exists():
        raise HTTPException(status_code=404, detail="Agent not found")
    
    os.remove(config_file)
    return {"status": "deleted", "name": agent_name}

# --- Execution & Logs ---
# (Dry run functionality removed)

# --- Authentication ---
@app.get("/api/auth/status/{agent_name}")
async def get_auth_status(agent_name: str):
    token_path = BASE_DIR / "data" / agent_name / "oauth_tokens.json"
    if token_path.exists():
        try:
            with open(token_path, "r") as f:
                token_data = json.load(f)
                creds = Credentials.from_authorized_user_info(token_data)
                
                if creds and creds.valid:
                    return {"valid": True, "message": "Token found and valid"}
                
                if creds and creds.expired and creds.refresh_token:
                    try:
                        # Attempt to refresh the token to see if it's still valid
                        creds.refresh(Request())
                        
                        # Save the refreshed token
                        with open(token_path, "w") as f_out:
                            f_out.write(creds.to_json())
                        
                        return {"valid": True, "message": "Token refreshed and valid"}
                    except Exception as e:
                        logger.warning(f"Token refresh failed for {agent_name}: {e}")
                        return {"valid": False, "message": "Token expired and refresh failed"}
                        
        except Exception as e:
            logger.error(f"Error checking auth status: {e}")
    
    return {"valid": False, "message": "Authentication required"}

@app.post("/api/auth/initiate/{agent_name}")
async def initiate_auth(agent_name: str):
    creds_path = BASE_DIR / "config" / "secrets" / "gmail_credentials.json"
    if not creds_path.exists():
        # Fallback to calendar credentials if gmail ones don't exist
        creds_path = BASE_DIR / "config" / "secrets" / "google_calendar_credentials.json"
        
    if not creds_path.exists():
        raise HTTPException(status_code=404, detail="OAuth credentials file not found in config/secrets/")

    scopes = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://mail.google.com/'
    ]
    
    flow = Flow.from_client_secrets_file(
        str(creds_path),
        scopes=scopes,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )
    
    auth_url, _ = flow.authorization_url(prompt='consent')
    return {"auth_url": auth_url}

@app.post("/api/auth/complete/{agent_name}")
async def complete_auth(agent_name: str, request: AuthCodeRequest):
    creds_path = BASE_DIR / "config" / "secrets" / "gmail_credentials.json"
    if not creds_path.exists():
        creds_path = BASE_DIR / "config" / "secrets" / "google_calendar_credentials.json"
        
    if not creds_path.exists():
        raise HTTPException(status_code=404, detail="OAuth credentials file not found")

    scopes = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://mail.google.com/'
    ]
    
    flow = Flow.from_client_secrets_file(
        str(creds_path),
        scopes=scopes,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )
    
    try:
        flow.fetch_token(code=request.code)
        creds = flow.credentials
        
        token_dir = BASE_DIR / "data" / agent_name
        token_dir.mkdir(parents=True, exist_ok=True)
        token_path = token_dir / "oauth_tokens.json"
        
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        
        os.chmod(token_path, 0o600)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to complete auth: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# --- Static Files ---

# Mount static files
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
