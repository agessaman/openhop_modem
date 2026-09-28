#pragma once

#include <stdint.h>

// A host frame is not available during a USB-host Ethernet experiment.
// Count continuous healthy Ethernet + radio time instead; a transient
// connection must not make a newly updated image permanent.
class OtaSanityPolicy {
public:
    void reset() { observing_ = false; healthySince_ = 0; }
    void observe(uint32_t now, bool healthy) {
        if (!healthy) { reset(); return; }
        if (!observing_) { healthySince_ = now; observing_ = true; }
    }
    bool healthyFor(uint32_t now, uint32_t duration) const {
        return observing_ && static_cast<uint32_t>(now - healthySince_) >= duration;
    }
private:
    bool observing_ = false;
    uint32_t healthySince_ = 0;
};
