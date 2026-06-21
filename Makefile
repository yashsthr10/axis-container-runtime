.PHONY: build run run-fastapi run-restart ps test format coverage clean clean-net

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

format:
	python3 -m black src tests examples

coverage:
	PYTHONPATH=src python3 -m coverage run --source=src/axis -m unittest discover -s tests/unit
	PYTHONPATH=src python3 -m coverage report -m

clean:
	rm -f src/runtime/axis-runtime .coverage
	rm -rf htmlcov

clean-net:
	sudo ip link delete axis0 2>/dev/null || true
