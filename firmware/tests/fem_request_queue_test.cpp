#include "fem_request_queue.h"

#include <cassert>
#include <iostream>
#include <vector>

namespace {

using FemRequests::Kind;
using Request = FemRequests::Request<uint8_t>;
using Queue = FemRequests::Queue<uint8_t, 4>;

Request get(uint8_t src) { return Request{ Kind::Get, 0, 0, src }; }
Request set(uint8_t apply, uint8_t value, uint8_t src) { return Request{ Kind::Set, apply, value, src }; }
Request error(uint8_t code, uint8_t src) { return Request{ Kind::Error, 0, code, src }; }

std::vector<Request> drain(Queue& queue, bool busy) {
    std::vector<Request> answered;
    queue.drain([&]() { return busy; }, [&](const Request& r) { answered.push_back(r); });
    return answered;
}

void testIdleAnswersImmediately() {
    Queue queue;
    assert(queue.push(set(0x01, 0x01, 7)));
    const auto answered = drain(queue, false);
    assert(answered.size() == 1);
    assert(answered[0].kind == Kind::Set);
    assert(answered[0].apply == 0x01 && answered[0].value == 0x01 && answered[0].src == 7);
    assert(queue.size() == 0);
}

void testGetAndErrorDoNotWait() {
    Queue queue;
    assert(queue.push(get(1)));
    assert(queue.push(error(0x06, 1)));
    const auto answered = drain(queue, true);
    assert(answered.size() == 2);
    assert(answered[0].kind == Kind::Get);
    assert(answered[1].kind == Kind::Error && answered[1].value == 0x06);
}

void testSetHoldsLaterRequestsInOrder() {
    Queue queue;
    assert(queue.push(get(1)));
    assert(queue.push(set(0x02, 0x02, 1)));
    assert(queue.push(get(2)));
    assert(queue.push(error(0x06, 1)));

    auto answered = drain(queue, true);
    assert(answered.size() == 1);
    assert(answered[0].kind == Kind::Get && answered[0].src == 1);
    assert(queue.size() == 3);

    answered = drain(queue, false);
    assert(answered.size() == 3);
    assert(answered[0].kind == Kind::Set);
    assert(answered[1].kind == Kind::Get && answered[1].src == 2);
    assert(answered[2].kind == Kind::Error);
    assert(queue.size() == 0);
}

void testFullQueueRejectsAndWraps() {
    Queue queue;
    for (uint8_t i = 0; i < 4; ++i) assert(queue.push(set(0x01, i & 0x01, i)));
    assert(!queue.push(get(9)));
    assert(drain(queue, true).empty());

    auto answered = drain(queue, false);
    assert(answered.size() == 4);
    for (uint8_t i = 0; i < 4; ++i) assert(answered[i].src == i);

    // Head has advanced; the ring must keep order across the wrap.
    assert(queue.push(set(0x01, 0x01, 10)));
    assert(queue.push(get(11)));
    answered = drain(queue, false);
    assert(answered.size() == 2);
    assert(answered[0].src == 10 && answered[1].src == 11);
}

}  // namespace

int main() {
    testIdleAnswersImmediately();
    testGetAndErrorDoNotWait();
    testSetHoldsLaterRequestsInOrder();
    testFullQueueRejectsAndWraps();
    std::cout << "fem request queue tests passed\n";
    return 0;
}
