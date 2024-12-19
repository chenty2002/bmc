#include "BMC.hpp"
#include "aig.hpp"
#include "basic.hpp"
#include <iostream>
#include <string>
#include <chrono>
using namespace std;
using namespace std::chrono;

int main(int argc, char **argv){
    auto t_begin = system_clock::now();

    cout<<"c USAGE: ./bmc <aig-file> [<option>|<property ID>]* "<<endl;
    Aiger *aiger = load_aiger_from_file(string(argv[1]));
    int property_index = 0;
    bool sc = 0, acc = 0;
    for (int i = 2; i < argc; ++i)
        property_index = (unsigned) atoi(argv[i]);
    BMC bmc(aiger, property_index, 999);
    bmc.initialize();
    int res_bmc = bmc.check(); 
    cout << res_bmc << endl;
   
    delete aiger;
    auto t_end = system_clock::now();
    auto duration = duration_cast<microseconds>(t_end - t_begin);
    double time_in_sec = double(duration.count()) * microseconds::period::num / microseconds::period::den;
    cout<<"c time = "<<time_in_sec<<endl;
    return 1;
}