#!/usr/bin/env python3
"""Host execution of real main network blocks with recording transport stubs.
No firmware emulation or hardware claims: tests boot/lazy-start decisions.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'src/main.cpp').read_text()
boot = main[main.index('    WifiManager::loadConfigOnly();', main.index('void setup()')):main.index('    // Hold the splash')]
lazy = main[main.index('    // Lazy TCP + OTA start'):main.index('    // PRG short-tap:')]
harness = r'''
#include <cassert>
#include <string>
#include "board_config.h"
using String = std::string;
struct { void println(const char*) {} } Serial;
namespace WifiManager {
struct Config { bool useStaticIP=false; int staticIP=0,gateway=0,subnet=0,dns1=0,dns2=0;
String tcpToken="persisted-test-token"; uint16_t tcpPort=5432; } cfg;
bool sta=false; int starts=0,loads=0;
void loadConfigOnly(){++loads;} const Config& getConfig(){return cfg;}
void begin(){++starts;} const char* getHostname(){return "saved-test-host";}
bool isSTAConnected(){return sta;}
}
namespace EthernetManager {
bool ip=false; int starts=0;
void begin(const char*, bool=false,int=0,int=0,int=0,int=0,int=0){++starts;}
bool hasIP(){return ip;} bool isLinkUp(){return ip;} void end(){}
}
namespace TCPServer { int starts=0; String token; unsigned port=0;
void begin(unsigned p,const String&t){++starts;port=p;token=t;} }
namespace OTAManager { int starts=0; String token;
void begin(const String& h,const String&t){assert(h=="saved-test-host");++starts;token=t;} }
bool tcpStarted=false,otaStarted=false; String deviceHostname;
void boot(){ BOOT }
void lazy(){ LAZY }
void reset(){tcpStarted=otaStarted=false; WifiManager::sta=false;
WifiManager::starts=WifiManager::loads=EthernetManager::starts=TCPServer::starts=OTAManager::starts=0;}
int main(){
#ifdef OPENHOP_USB_ECM
assert(!BOARD.has_wifi);
for(bool ipAtBoot:{false,true}) {
reset(); EthernetManager::ip=ipAtBoot; boot();
assert(WifiManager::loads==1 && WifiManager::starts==0);
assert(EthernetManager::starts==1);
assert(tcpStarted==ipAtBoot && otaStarted==ipAtBoot);
lazy(); assert(WifiManager::starts==0);
EthernetManager::ip=true; lazy();
assert(tcpStarted && otaStarted);
assert(TCPServer::token==WifiManager::cfg.tcpToken);
assert(OTAManager::token==WifiManager::cfg.tcpToken);
assert(TCPServer::port==5432);
EthernetManager::ip=false; lazy(); EthernetManager::ip=true; lazy();
assert(TCPServer::starts==1 && OTAManager::starts==1);
}
#else
assert(BOARD.has_wifi); reset(); EthernetManager::ip=false; boot();
assert(WifiManager::starts==1 && !otaStarted);
WifiManager::sta=true; lazy(); assert(tcpStarted && otaStarted);
assert(TCPServer::token==WifiManager::cfg.tcpToken);
#endif
}
'''.replace('BOOT', boot).replace('LAZY', lazy)
with tempfile.TemporaryDirectory(prefix='openhop-ethernet-only-') as tmp:
    src = Path(tmp) / 'main.cpp'
    src.write_text(harness)
    for defines in [('BOARD_HELTEC_V42_USB_ETH', 'OPENHOP_USB_ECM'), ('BOARD_HELTEC_V42',)]:
        exe = Path(tmp) / defines[0]
        subprocess.run(['c++', '-std=c++17', '-I', str(ROOT / 'include'), *['-D'+d for d in defines], str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
print('Ethernet-only and standard V4.2 boot/lazy-start control flow: PASS')
