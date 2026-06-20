#pragma once

#include <map>
#include <string>
#include <vector>

struct RuntimeConfig {
    std::string name;
    std::string rootfs;
    std::string hostname;
    std::string workdir;
    std::vector<std::string> command;
    std::map<std::string, std::string> env;
    std::string cgroupPath;
    std::string memory;
    std::string cpu;
};

RuntimeConfig loadRuntimeConfig(const std::string& path);
