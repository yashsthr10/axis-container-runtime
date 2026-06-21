CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Wpedantic -O2

.PHONY: all clean

all: axis-runtime

axis-runtime: Container.cpp runtime_config.cpp runtime_config.hpp
	$(CXX) $(CXXFLAGS) Container.cpp runtime_config.cpp -o axis-runtime

clean:
	rm -f axis-runtime
