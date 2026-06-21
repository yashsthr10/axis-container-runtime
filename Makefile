.PHONY: build run run-fastapi run-restart ps test clean clean-net

build:
	$(MAKE) -C src/runtime

run: build
	sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile

run-fastapi: build
	sudo PYTHONPATH=src python3 -m axis.cli run -f examples/fastapi/Axisfile

run-restart: build
	sudo PYTHONPATH=src python3 -m axis.cli run -f examples/restart/Axisfile

ps:
	PYTHONPATH=src python3 -m axis.cli ps

test:
	PYTHONPATH=src python3 -m unittest discover -s tests/unit

clean:
	rm -f src/runtime/axis-runtime

clean-net:
	sudo ip link delete axis0 2>/dev/null || true
