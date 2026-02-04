"""
Configuration Loader for MAE

Loads and validates YAML configuration files for agents.
Supports environment variable substitution for sensitive values.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class ConfigLoader:
    """Load and validate agent configurations"""
    
    REQUIRED_FIELDS = {
        'agent': ['name', 'schedule_interval_minutes', 'enabled'],
        'email': ['provider', 'address'],
        'logging': ['level', 'file']
    }
    
    DEFAULT_VALUES = {
        'deletion': {
            'action_on_deletion': 'move_to_trash',  # 'move_to_trash' or 'apply_label'
            'delete_promotional': True,
            'dry_run': True
        },

        'calendar': {
            'enabled': False
        },
        'classification': {
            'topics_i_care_about': [],
            'whitelisted_senders': [],
            'blacklisted_senders': []
        }
    }
    
    def __init__(self, config_path: str):
        """
        Initialize config loader
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        self.config = self._load_yaml()
        self._apply_defaults()
        self._validate()
        self._resolve_paths()
    
    def _load_yaml(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                raise ConfigurationError("Configuration file is empty")
            
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML syntax: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")
    
    def _apply_defaults(self):
        """Apply default values for missing optional fields"""
        for section, defaults in self.DEFAULT_VALUES.items():
            if section not in self.config:
                self.config[section] = defaults.copy()
            else:
                # Merge defaults with existing config
                for key, value in defaults.items():
                    if key not in self.config[section]:
                        self.config[section][key] = value
    
    def _validate(self):
        """Validate required fields are present"""
        # Validate required fields are present
        agent_section = self.config.get('agent', {})
        if 'name' not in agent_section:
            raise ConfigurationError("Missing required field: agent.name")
            
        agent_type = agent_section.get('type', 'email')
        
        # Common required fields
        if 'schedule_interval_minutes' not in agent_section:
             raise ConfigurationError("Missing required field: agent.schedule_interval_minutes")
             
        if 'logging' not in self.config:
             raise ConfigurationError("Missing required section: logging")

        # Type specific validation
        if agent_type == 'email':
            if 'email' not in self.config:
                raise ConfigurationError("Missing required section: email")
            if 'address' not in self.config['email']:
                raise ConfigurationError("Missing required field: email.address")
        
        # Validate specific field types and values
        if self.config['agent']['schedule_interval_minutes'] < 1:
            raise ConfigurationError("schedule_interval_minutes must be >= 1")
        
        if agent_type == 'email' and self.config['email']['provider'] not in ['gmail']:
            logger.warning(
                f"Email provider '{self.config['email']['provider']}' is not yet supported. "
                f"Only 'gmail' is currently implemented."
            )
    
    def _resolve_paths(self):
        """Resolve relative paths to absolute paths"""
        project_root = Path(__file__).parent.parent.parent
        

        
        # Resolve log file path
        log_file = Path(self.config['logging']['file'])
        if not log_file.is_absolute():
            self.config['logging']['file'] = str(project_root / log_file)
        
        # Create data directory for agent
        agent_name = self.config['agent']['name']
        self.agent_data_dir = project_root / 'data' / agent_name
        self.agent_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Set paths for agent data
        self.email_cache_dir = self.agent_data_dir / 'emails'
        self.email_cache_dir.mkdir(exist_ok=True)
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get configuration value
        
        Args:
            section: Configuration section name
            key: Optional key within section
            default: Default value if not found
        
        Returns:
            Configuration value or default
        """
        if section not in self.config:
            return default
        
        if key is None:
            return self.config[section]
        
        return self.config[section].get(key, default)
    
    def get_agent_name(self) -> str:
        """Get agent name"""
        return self.config['agent']['name']
    
    def is_enabled(self) -> bool:
        """Check if agent is enabled"""
        return self.config['agent']['enabled']
    
    def get_schedule_interval(self) -> int:
        """Get schedule interval in minutes"""
        return self.config['agent']['schedule_interval_minutes']
    
    def __repr__(self) -> str:
        return f"ConfigLoader(agent={self.get_agent_name()}, config={self.config_path})"


def load_config(config_path: str) -> ConfigLoader:
    """
    Load configuration from file
    
    Args:
        config_path: Path to YAML configuration file
    
    Returns:
        ConfigLoader instance
    """
    return ConfigLoader(config_path)


if __name__ == "__main__":
    # Test configuration loading
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python config_loader.py <config_path>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        config = load_config(sys.argv[1])
        print(f"\n✓ Configuration loaded successfully: {config}")
        print(f"\nAgent: {config.get_agent_name()}")
        print(f"Enabled: {config.is_enabled()}")
        print(f"Schedule: Every {config.get_schedule_interval()} minutes")
        print(f"Email: {config.get('email', 'address')}")
        print(f"Data directory: {config.agent_data_dir}")
    
    except ConfigurationError as e:
        print(f"\n✗ Configuration error: {e}")
        sys.exit(1)
