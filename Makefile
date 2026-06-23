# HUB75 Clock - Makefile
# Run from the repo root on the Pi
# Usage: make <target>

.PHONY: update logs restart status stop start test config install rgb theme-builder sprite-builder ld2410-tuner

update:
	~/update-clock.sh

logs:
	sudo journalctl -u hub75-clock -f --no-pager

restart:
	sudo systemctl restart hub75-clock

status:
	sudo systemctl status hub75-clock

stop:
	@echo "Stopping hub75-clock..."
	@if ! timeout 10 sudo systemctl stop hub75-clock; then \
		echo "hub75-clock did not stop within 10s; forcing SIGKILL..."; \
		sudo systemctl kill -s SIGKILL hub75-clock || true; \
	fi
	@echo "Stopping hub75-ld2410-tuner..."
	@timeout 5 sudo systemctl stop hub75-ld2410-tuner || sudo systemctl kill -s SIGKILL hub75-ld2410-tuner || true

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
	python3 tools/theme-server.py --themes-dir themes --sprites-dir sprites --animations-dir sprite-animations

sprite-builder:
	python3 tools/theme-server.py --themes-dir themes --sprites-dir sprites --animations-dir sprite-animations

ld2410-tuner:
	python3 tools/ld2410-web-tuner.py --host 0.0.0.0 --web-port 8766
