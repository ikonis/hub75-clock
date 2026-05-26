# HUB75 Clock - Makefile
# Run from the repo root on the Pi
# Usage: make <target>

.PHONY: update logs restart status stop start test config install rgb theme-builder sprite-builder

update:
	~/update-clock.sh

logs:
	sudo journalctl -u hub75-clock -f --no-pager

restart:
	sudo systemctl restart hub75-clock

status:
	sudo systemctl status hub75-clock

stop:
	sudo systemctl stop hub75-clock

start:
	sudo systemctl start hub75-clock

test:
	sudo python3 /opt/hub75-clock/test_sensors.py

config:
	bash scripts/configure.sh

rgb:
	sudo python3 scripts/test_display.py

install:
	bash install.sh

theme-builder:
	python3 tools/theme-server.py --themes-dir themes --sprites-dir sprites

sprite-builder:
	python3 tools/theme-server.py --themes-dir themes --sprites-dir sprites
