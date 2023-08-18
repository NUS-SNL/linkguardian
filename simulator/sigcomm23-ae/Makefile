PARENT_DIR := $(abspath $(CURDIR)/..)
LG=docker run -it -v $(PARENT_DIR):/root lg-sim:sigcomm23ae
LG_PARALLEL=docker run -t -v $(PARENT_DIR):/root lg-sim:sigcomm23ae

all: reproducibility

reproducibility: simulate_all process_all plot_all

functionality_50: simulate_50 process_50 plot_50

functionality_75: simulate_75 process_75 plot_75

plot_50:
	$(LG) bash -c "cd sigcomm23-ae/gnuplot_scripts/functionality; gnuplot sim_combined_50_75.plt && gnuplot total_penalty_ratio.plt && gnuplot diff_min_pod_capacity.plt"

plot_75:
	$(LG) bash -c "cd sigcomm23-ae/gnuplot_scripts/reproducibility; gnuplot sim_combined_50_75.plt && gnuplot total_penalty_ratio.plt && gnuplot diff_min_pod_capacity.plt"

plot_all:
	$(LG) bash -c "cd sigcomm23-ae/gnuplot_scripts/reproducibility; gnuplot sim_combined_50_75.plt && gnuplot total_penalty_ratio.plt && gnuplot diff_min_pod_capacity.plt"

process_50:
	$(LG) bash -c "cd data_analysis; ./calc_data_for_cdfs.py ../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_50.dat ../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_50.dat"

process_75:
	$(LG) bash -c "cd data_analysis; ./calc_data_for_cdfs.py ../output_files/sigcomm23_eval/fbfabric_100k_os1-corropt_75.dat ../output_files/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_75.dat"

process_all: process_50 process_75

simulate_50:
	$(LG) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-corropt_50.json
	$(LG) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_50.json

simulate_75:
	$(LG) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-corropt_75.json
	$(LG) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_75.json

simulate_50_parallel:
	@echo "Simulation for 50% capacity constraint running in parallel, please check the running "python3" processes. This should take about 10 minutes. Please leave this terminal up and running." 
	$(LG_PARALLEL) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-corropt_50.json > /dev/null & \
	$(LG_PARALLEL) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_50.json > /dev/null & \
	wait; 
	@echo "Simulation for 50% capacity constraint completed!"

simulate_75_parallel:
	@echo "Simulation for 75% capacity constraint running in parallel, please check the running "python3" processes. This should take about 6 hours. Please leave this terminal up and running." 
	$(LG_PARALLEL) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-corropt_75.json > /dev/null & \
	$(LG_PARALLEL) ./main.py ./simulation_configs/sigcomm23_eval/fbfabric_100k_os1-lg_corropt_75.json > /dev/null & \
	wait; 
	@echo "Simulation for 75% capacity constraint completed!"

simulate_all: simulate_50 simulate_75

generate_trace:
	$(LG) bash -c "cd trace_generator && ./generate_loss_trace.py ./input_files/sigcomm23_eval/fbfabric_100k_os1_mttf10k.json"

build_container:
	docker build -t lg-sim:sigcomm23ae .
