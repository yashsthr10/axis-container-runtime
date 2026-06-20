.PHONY: build run ps test clean clean-net

build:
	$(MAKE) -C runtime

run: build
	sudo python3 -m axis.cli run

ps:
	python3 -m axis.cli ps

test:
	python3 -m unittest discover -s tests/unit

clean:
	rm -f runtime/axis-runtime namespace_test

clean-net:
	sudo ip link delete axis0 2>/dev/null || true
