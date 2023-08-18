Configuring and using the intel_pstate power scaling driver

- This driver only provides two possible governors: performance and powersave
- 1-time config to change to the performance governor: sudo cpupower frequency-set -g performance
- Check using this command: sudo cpupower frequency-info (see the "current policy" section)
Changing to performance mode: 
```
sudo cpupower idle-set -d 3
sudo cpupower idle-set -d 2
sudo cpupower idle-set -d 1
```

- Check using sudo i7z. All cores should be running in the C0 state for 100% time. Might need to wait a few seconds until all cores run in C0 state. 
Change back to normal mode: sudo cpupower idle-set -E
- Check using sudo i7z. All cores should be running in the lower states especially C6. Might need to wait a few seconds until all cores move away from the C0 state.


