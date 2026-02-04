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

class AppPasswordRequest(BaseModel):
    email: str
    app_password: str

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

# App Password Credentials Management
@app.get("/api/auth/credentials/{agent_name}")
async def get_credential_status(agent_name: str):
    """Check if app password credentials are configured"""
    from src.utils.credential_manager import CredentialManager
    
    has_cred = CredentialManager.has_credential(agent_name, "gmail")
    if has_cred:
        creds = CredentialManager.get_credential(agent_name, "gmail")
        return {
            "configured": True,
            "email": creds.get("email"),
            "auth_method": "app_password"
        }
    return {"configured": False, "auth_method": None}

@app.post("/api/auth/credentials/{agent_name}")
async def store_credentials(agent_name: str, request: AppPasswordRequest):
    """Store Gmail app password credentials"""
    from src.utils.credential_manager import CredentialManager
    
    try:
        # Validate email
        CredentialManager.validate_email(request.email)
        
        # Validate and normalize password
        clean_password = CredentialManager.validate_password(request.app_password)
        
        # Store credentials
        CredentialManager.store_credential(
            agent_name,
            "gmail",
            {
                "email": request.email.strip().lower(),
                "password": clean_password
            }
        )
        
        return {
            "status": "success",
            "message": "Credentials stored successfully",
            "email": request.email.strip().lower()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to store credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to store credentials")

@app.delete("/api/auth/credentials/{agent_name}")
async def delete_credentials(agent_name: str):
    """Delete app password credentials"""
    from src.utils.credential_manager import CredentialManager
    
    try:
        CredentialManager.delete_credential(agent_name, "gmail")
        return {"status": "success", "message": "Credentials deleted"}
    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete credentials")

@app.post("/api/auth/test/{agent_name}")
async def test_connection(agent_name: str):
    """Test Gmail IMAP connection"""
    from src.utils.credential_manager import CredentialManager
    from src.agents.email import GmailClient
    
    creds = CredentialManager.get_credential(agent_name, "gmail")
    if not creds:
        raise HTTPException(status_code=404, detail="No credentials found")
    
    try:
        client = GmailClient(
            email_address=creds['email'],
            app_password=creds['password'],
            agent_name=agent_name
        )
        client.connect()
        client.disconnect()
        
        return {
            "status": "success",
            "message": f"Successfully connected to {creds['email']}"
        }
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {
            "status": "error",
            "message": f"Connection failed: {str(e)}"
        }

# --- Static Files ---

# Mount static files
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
