"""
Main Orchestrator for MAE

Manages agent scheduling and execution.
"""

import logging
import time
import signal
import sys
from typing import Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestrator for MAE agents"""
    
    def __init__(self, config_dir: Path):
        """
        Initialize orchestrator
        
        Args:
            config_dir: Directory containing agent configurations
        """
        self.config_dir = Path(config_dir)
        self.running = False
        self.agents = []
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Orchestrator initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
        # Release all tokens
        if hasattr(self, 'token_manager') and self.token_manager:
            logger.info("Releasing all tokens...")
            self.token_manager.release_all()
            
        logger.info("Exiting...")
        sys.exit(0)
    
    def load_agents(self):
        """Load all agent configurations"""
        from src.core import load_config
        from src.orchestrator import TokenManager
        
        # Initialize token manager
        self.token_manager = TokenManager()
        
        # Find all agent configs
        config_files = list(self.config_dir.glob("*.yaml"))
        config_files = [f for f in config_files if not f.name.endswith('.example')]
        
        logger.info(f"Found {len(config_files)} agent configuration(s)")
        
        for config_file in config_files:
            try:
                # Load config
                config = load_config(str(config_file))
                
                # Check if agent is enabled
                if not config.is_enabled():
                    logger.info(f"Agent {config.get_agent_name()} is disabled, skipping")
                    continue
                
                # Create agent based on type
                # Default to 'email' if no type specified in agent section
                agent_type = config.get('agent', 'type', 'email')
                
                if agent_type == 'email':
                    from src.agents.email_agent import EmailAgent
                    agent = EmailAgent(config, self.token_manager)
                    self.agents.append({
                        'name': config.get_agent_name(),
                        'type': agent_type,
                        'instance': agent,
                        'interval': config.get_schedule_interval(),
                        'last_run': None
                    })
                    logger.info(f"Loaded email agent: {config.get_agent_name()}")
                else:
                    logger.warning(f"Unknown agent type: {agent_type}")
            
            except Exception as e:
                logger.error(f"Failed to load agent from {config_file}: {e}", exc_info=True)
        
        logger.info(f"Loaded {len(self.agents)} active agent(s)")
    
    def run(self, once: bool = False):
        """
        Run the orchestrator
        
        Args:
            once: If True, run agents once and exit. If False, run in loop.
        """
        logger.info("Starting orchestrator")
        self.running = True
        
        if not self.agents:
            logger.warning("No agents loaded! Orchestrator will run idle.")

        
        if once:
            logger.info("Running in single-run mode")
            self._run_all_agents()
            logger.info("Single run complete")
        else:
            logger.info("Running in continuous mode")
            self._run_loop()
    
    def _run_loop(self):
        """Main orchestrator loop"""
        while self.running:
            try:
                # Check which agents need to run
                for agent_info in self.agents:
                    if self._should_run_agent(agent_info):
                        self._run_agent(agent_info)
                
                # Sleep for a short interval
                time.sleep(60)  # Check every minute
            
            except Exception as e:
                logger.error(f"Error in orchestrator loop: {e}", exc_info=True)
                time.sleep(60)  # Wait before retrying
        
        logger.info("Orchestrator stopped")
    
    def _run_all_agents(self):
        """Run all agents once"""
        for agent_info in self.agents:
            self._run_agent(agent_info)
    
    def _should_run_agent(self, agent_info: Dict[str, Any]) -> bool:
        """Check if agent should run based on schedule"""
        last_run = agent_info['last_run']
        interval = agent_info['interval']
        
        if last_run is None:
            return True  # Never run before
        
        time_since_last_run = (datetime.now() - last_run).total_seconds() / 60
        return time_since_last_run >= interval
    
    def _run_agent(self, agent_info: Dict[str, Any]):
        """Run a single agent, reloading config first"""
        agent_name = agent_info['name']
        
        # Reload configuration to pick up any changes from the dashboard
        from src.core import load_config
        config_file = self.config_dir / f"{agent_name}.yaml"
        
        try:
            config = load_config(str(config_file))
            
            if not config.is_enabled():
                logger.info(f"Agent {agent_name} is now disabled, skipping")
                agent_info['last_run'] = datetime.now()
                return

            # Re-instantiate agent with new config
            agent_type = config.get('agent', 'type', 'email')
            if agent_type == 'email':
                from src.agents.email_agent import EmailAgent
                agent = EmailAgent(config, self.token_manager)
                agent_info['instance'] = agent
                agent_info['interval'] = config.get_schedule_interval()
            else:
                logger.warning(f"Unknown agent type: {agent_type}")
                return

            logger.info(f"Running agent: {agent_name}")
            start_time = datetime.now()
            
            agent.run()
            agent_info['last_run'] = datetime.now()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.debug(f"Agent {agent_name} completed in {duration:.1f}s")
        
        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}", exc_info=True)
            # Still update last_run to avoid immediate retry
            agent_info['last_run'] = datetime.now()


def main():
    """Main entry point"""
    import argparse
    
    # Setup logging
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Setup logging
    log_filename = f"logs/mae_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    logger.info(f"Logging to {log_filename}")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='MAE Email Processing Orchestrator')
    parser.add_argument(
        '--config-dir',
        default='config/agents',
        help='Directory containing agent configurations (default: config/agents)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run agents once and exit (default: run in loop)'
    )
    parser.add_argument(
        '--start-date',
        help='Start date for historical processing (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        help='End date for historical processing (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--target-labels',
        help='Comma-separated list of target labels for historical processing (e.g. promotions)'
    )
    parser.add_argument(
        '--no-server',
        action='store_true',
        help='Disable the management server dashboard'
    )
    
    args = parser.parse_args()
    
    # Create and run orchestrator
    # Create and run orchestrator
    orchestrator = Orchestrator(args.config_dir)
    orchestrator.load_agents()
    
    # Check for historical processing mode
    if args.start_date and args.end_date and args.target_labels:
        logger.info("Running in historical processing mode")
        
        # Find email agent
        email_agent = None
        for agent_info in orchestrator.agents:
            if agent_info['type'] == 'email':
                email_agent = agent_info['instance']
                break
        
        if not email_agent:
            logger.error("No email agent found for historical processing")
            return
            
        target_labels = [l.strip() for l in args.target_labels.split(',')]
        email_agent.process_historical_emails(
            args.start_date,
            args.end_date,
            target_labels
        )
        return

    # Start Management Server
    if not args.no_server:
        import uvicorn
        import threading
        from src.server.app import app
        
        def run_server():
            # Ensure standard logging levels are defined (sometimes libraries rename them)
            for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                if hasattr(logging, level):
                    logging.addLevelName(getattr(logging, level), level)
            
            logger.info("Starting Management Server on http://0.0.0.0:8000")
            # Use log_config=None to avoid uvicorn trying to reconfigure logging
            # which fails if standard level names like 'INFO' were modified.
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error", log_config=None)
            
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    orchestrator.run(once=args.once)


if __name__ == "__main__":
    main()
