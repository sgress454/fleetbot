python3 create_systemd_conf.py
sudo cp systemd.conf /etc/systemd/system/fleetbot.service
sudo systemctl daemon-reload
sudo systemctl enable fleetbot.service
sudo systemctl start fleetbot.service
rm systemd.conf