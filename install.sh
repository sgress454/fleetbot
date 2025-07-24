python3 create_supervisor_conf.py
sudo cp supervisor.conf /etc/supervisor/conf.d/fleetbot.conf
sudo supervisorctl reread
sudo supervisorctl update