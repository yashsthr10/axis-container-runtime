#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "runtime_config.hpp"

#include <sched.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

struct ChildArgs {
    int syncPipeRead;
    const RuntimeConfig* config;
};

bool writeFile(const std::string& path, const std::string& value)
{
    FILE* file = fopen(path.c_str(), "w");
    if (!file) {
        std::cerr << "Failed to open " << path << ": " << strerror(errno) << "\n";
        return false;
    }

    bool ok = fwrite(value.data(), 1, value.size(), file) == value.size();
    fclose(file);
    return ok;
}

std::string parentPath(const std::string& path)
{
    size_t slash = path.find_last_of('/');
    if (slash == std::string::npos || slash == 0) {
        return "/";
    }
    return path.substr(0, slash);
}

bool mkdirRecursive(const std::string& path, mode_t mode)
{
    std::string current;
    for (char c : path) {
        current.push_back(c);
        if (c != '/') {
            continue;
        }
        if (current.size() > 1 && mkdir(current.c_str(), mode) == -1 && errno != EEXIST) {
            return false;
        }
    }

    return mkdir(path.c_str(), mode) != -1 || errno == EEXIST;
}

void enableController(const std::string& cgroupPath, const std::string& controller)
{
    std::string subtreeControl = cgroupPath + "/cgroup.subtree_control";
    if (!writeFile(subtreeControl, "+" + controller)) {
        std::cerr << "Warning: could not enable cgroup controller " << controller
                  << " in " << cgroupPath << "\n";
    }
}

bool setupCgroup(pid_t pid, const RuntimeConfig& config)
{
    std::string parent = parentPath(config.cgroupPath);
    if (!mkdirRecursive(parent, 0755)) {
        std::cerr << "Failed to create cgroup parent " << parent << ": " << strerror(errno) << "\n";
        return false;
    }

    // Enable controllers in the root and Axis parent cgroup so limit files are
    // created in child cgroups on cgroup v2 systems.
    enableController("/sys/fs/cgroup", "memory");
    enableController("/sys/fs/cgroup", "cpu");
    enableController(parent, "memory");
    enableController(parent, "cpu");

    if (!mkdirRecursive(config.cgroupPath, 0755)) {
        std::cerr << "Failed to create cgroup " << config.cgroupPath << ": " << strerror(errno) << "\n";
        return false;
    }

    if (!config.memory.empty() && !writeFile(config.cgroupPath + "/memory.max", config.memory)) {
        std::cerr << "Warning: memory limit was not applied\n";
    }

    if (!config.cpu.empty() && !writeFile(config.cgroupPath + "/cpu.max", config.cpu)) {
        std::cerr << "Warning: CPU limit was not applied\n";
    }

    return writeFile(config.cgroupPath + "/cgroup.procs", std::to_string(pid));
}

int child(void* arg)
{
    ChildArgs* childArgs = static_cast<ChildArgs*>(arg);
    const RuntimeConfig& config = *childArgs->config;
    char startSignal;

    if (read(childArgs->syncPipeRead, &startSignal, 1) != 1) {
        std::cerr << "Failed to receive start signal: " << strerror(errno) << "\n";
        close(childArgs->syncPipeRead);
        return 1;
    }
    close(childArgs->syncPipeRead);

    if (sethostname(config.hostname.c_str(), config.hostname.size()) == -1) {
        std::cerr << "sethostname failed: " << strerror(errno) << "\n";
        return 1;
    }

    if (mount(nullptr, "/", nullptr, MS_REC | MS_PRIVATE, nullptr) == -1) {
        std::cerr << "mount propagation setup failed: " << strerror(errno) << "\n";
        return 1;
    }

    if (chroot(config.rootfs.c_str()) == -1) {
        std::cerr << "chroot failed: " << strerror(errno) << "\n";
        return 1;
    }

    if (chdir(config.workdir.c_str()) == -1) {
        std::cerr << "chdir failed: " << strerror(errno) << "\n";
        return 1;
    }

    if (mkdir("/proc", 0555) == -1 && errno != EEXIST) {
        std::cerr << "mkdir /proc failed: " << strerror(errno) << "\n";
        return 1;
    }

    if (mount("proc", "/proc", "proc", 0, nullptr) == -1) {
        std::cerr << "mount /proc failed: " << strerror(errno) << "\n";
        return 1;
    }

    for (const auto& [key, value] : config.env) {
        setenv(key.c_str(), value.c_str(), 1);
    }

    std::vector<char*> argv;
    for (const std::string& part : config.command) {
        argv.push_back(const_cast<char*>(part.c_str()));
    }
    argv.push_back(nullptr);

    execvp(argv[0], argv.data());
    std::cerr << "execvp failed: " << strerror(errno) << "\n";
    return 1;
}

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::cerr << "Usage: axis-runtime <runtime-config.json>\n";
        return 1;
    }

    RuntimeConfig config;
    try {
        config = loadRuntimeConfig(argv[1]);
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << "\n";
        return 1;
    }

    if (config.command.empty()) {
        std::cerr << "Runtime config command cannot be empty\n";
        return 1;
    }

    const int stackSize = 1024 * 1024;
    int syncPipe[2];

    if (pipe(syncPipe) == -1) {
        std::cerr << "pipe failed: " << strerror(errno) << "\n";
        return 1;
    }

    std::vector<char> stack(stackSize);
    ChildArgs childArgs{syncPipe[0], &config};

    pid_t pid = clone(
        child,
        stack.data() + stack.size(),
        CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWNET | SIGCHLD,
        &childArgs
    );

    if (pid == -1) {
        std::cerr << "clone failed: " << strerror(errno) << "\n";
        close(syncPipe[0]);
        close(syncPipe[1]);
        return 1;
    }

    std::cout << "AXIS_PID " << pid << "\n" << std::flush;
    close(syncPipe[0]);

    if (!setupCgroup(pid, config)) {
        close(syncPipe[1]);
        waitpid(pid, nullptr, 0);
        return 1;
    }

    if (write(syncPipe[1], "1", 1) != 1) {
        std::cerr << "Failed to send start signal: " << strerror(errno) << "\n";
        close(syncPipe[1]);
        waitpid(pid, nullptr, 0);
        return 1;
    }
    close(syncPipe[1]);

    int status = 0;
    waitpid(pid, &status, 0);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
