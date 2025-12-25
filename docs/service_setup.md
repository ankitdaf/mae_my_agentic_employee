# Setting up MAE as a System Service

To ensure MAE runs continuously and starts automatically on boot, you can set it up as a `systemd` service.

## 1. Create the Service File

Create a new service file at `/etc/systemd/system/mae-agent.service` with the following content. 

> [!NOTE]
> Adjust the `User` and `WorkingDirectory` paths if they differ on your system.

```ini
[Unit]
Description=MAE Agentic Employee Service
After=network.target

[Service]
Type=simple
User=<user>
WorkingDirectory=/path/to/mae
# Using a wrapper script to handle conda activation
ExecStart=/bin/bash /path/to/mae/scripts/run_agent.sh
Restart=always
RestartSec=10
# Environment variables
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

## 2. Prepare the Wrapper Script

The service uses a wrapper script to handle the Conda environment activation. Ensure `scripts/run_agent.sh` exists and is executable:

```bash
chmod +x scripts/run_agent.sh
```

The script content should look like this (adjust the Conda path as needed):

```bash
#!/bin/bash

# Source conda
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
    echo "Conda not found!"
    exit 1
fi

# Activate environment
conda activate rknn

# Ensure we are in the correct directory
cd /path/to/mae

# Run orchestrator
python3 -m src.orchestrator.main
```

## 3. Enable and Start the Service

Run the following commands to enable and start the service:

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable mae-agent

# Start the service now
sudo systemctl start mae-agent
```

## 4. Monitoring the Service

You can check the status and logs of the service using `systemctl` and `journalctl`:

```bash
# Check status
sudo systemctl status mae-agent

# View real-time logs
sudo journalctl -u mae-agent -f
```
