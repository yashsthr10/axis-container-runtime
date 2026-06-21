#include "runtime_config.hpp"

#include <cctype>
#include <fstream>
#include <stdexcept>

namespace {

class Json {
public:
    explicit Json(std::string text) : text_(std::move(text)) {}

    std::string stringValue(const std::string& key, bool required = true)
    {
        size_t pos = valueStart(key, required);
        if (pos == std::string::npos) {
            return "";
        }
        if (text_.compare(pos, 4, "null") == 0) {
            return "";
        }
        return parseString(pos);
    }

    std::vector<std::string> stringArray(const std::string& key)
    {
        size_t pos = valueStart(key, true);
        expect(pos, '[');
        ++pos;

        std::vector<std::string> values;
        while (true) {
            skipWhitespace(pos);
            if (text_.at(pos) == ']') {
                return values;
            }
            values.push_back(parseString(pos));
            skipWhitespace(pos);
            if (text_.at(pos) == ',') {
                ++pos;
                continue;
            }
            expect(pos, ']');
            return values;
        }
    }

    std::map<std::string, std::string> stringMap(const std::string& key, bool required = true)
    {
        size_t pos = valueStart(key, required);
        if (pos == std::string::npos) {
            return {};
        }
        expect(pos, '{');
        ++pos;

        std::map<std::string, std::string> values;
        while (true) {
            skipWhitespace(pos);
            if (text_.at(pos) == '}') {
                return values;
            }

            std::string mapKey = parseString(pos);
            skipWhitespace(pos);
            expect(pos, ':');
            ++pos;
            skipWhitespace(pos);
            values[mapKey] = parseString(pos);
            skipWhitespace(pos);

            if (text_.at(pos) == ',') {
                ++pos;
                continue;
            }
            expect(pos, '}');
            return values;
        }
    }

private:
    size_t valueStart(const std::string& key, bool required)
    {
        std::string quotedKey = "\"" + key + "\"";
        size_t pos = text_.find(quotedKey);
        if (pos == std::string::npos) {
            if (required) {
                throw std::runtime_error("Missing runtime config key: " + key);
            }
            return std::string::npos;
        }

        pos = text_.find(':', pos + quotedKey.size());
        if (pos == std::string::npos) {
            throw std::runtime_error("Invalid runtime config key: " + key);
        }
        ++pos;
        skipWhitespace(pos);
        return pos;
    }

    std::string parseString(size_t& pos)
    {
        expect(pos, '"');
        ++pos;

        std::string value;
        while (pos < text_.size()) {
            char c = text_.at(pos++);
            if (c == '"') {
                return value;
            }
            if (c == '\\') {
                if (pos >= text_.size()) {
                    throw std::runtime_error("Invalid escape sequence");
                }
                char escaped = text_.at(pos++);
                if (escaped == 'n') {
                    value.push_back('\n');
                } else if (escaped == 't') {
                    value.push_back('\t');
                } else {
                    value.push_back(escaped);
                }
            } else {
                value.push_back(c);
            }
        }

        throw std::runtime_error("Unterminated string");
    }

    void skipWhitespace(size_t& pos)
    {
        while (pos < text_.size() && std::isspace(static_cast<unsigned char>(text_.at(pos)))) {
            ++pos;
        }
    }

    void expect(size_t pos, char expected)
    {
        if (pos >= text_.size() || text_.at(pos) != expected) {
            throw std::runtime_error(std::string("Expected '") + expected + "'");
        }
    }

    std::string text_;
};

} // namespace

RuntimeConfig loadRuntimeConfig(const std::string& path)
{
    std::ifstream file(path);
    if (!file) {
        throw std::runtime_error("Failed to open runtime config: " + path);
    }

    std::string text((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    Json json(text);

    RuntimeConfig config;
    config.name = json.stringValue("name");
    config.rootfs = json.stringValue("rootfs");
    config.hostname = json.stringValue("hostname");
    config.workdir = json.stringValue("workdir");
    config.command = json.stringArray("command");
    config.env = json.stringMap("env");
    config.bindMounts = json.stringMap("bind_mounts", false);
    config.cgroupPath = json.stringValue("cgroup_path");
    config.memory = json.stringValue("memory", false);
    config.cpu = json.stringValue("cpu", false);
    return config;
}
