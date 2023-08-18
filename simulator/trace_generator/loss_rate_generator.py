import json
import random
import tabulate

FRACTION_DECIMAL_PLACES = 2
PERCENT_FRACTION_GRANULARITY = round(pow(10, -FRACTION_DECIMAL_PLACES), FRACTION_DECIMAL_PLACES)

class LossRateGenerator(object):
    def __init__(self, json_dist_file: str):
        """ 
        Initializes the the LossRateGenerator object using the distribution from
        the JSON file

        Arguments:
            json_dist_file: str. path to a JSON file with loss rate distribution data
        """
        self.json_dist_file = json_dist_file

        # load the json file in a dict
        fin_json = open(json_dist_file, 'r')
        json_dict = json.load(fin_json)
        fin_json.close()

        # get the name of the distribution/trace
        self.dist_name = json_dict['dist_name'] 

        # Populate the distribution dict
        # key: tuple (start, end) | val: tuple of the loss rate bucket (range)
        # e.g. (0, 47.23): (1e-8, 9e-6)
        # assumes that the distribution buckets from the JSON 
        # have an increasing order of loss rates
        self.dist_dict = {}

        # key: tuple. (loss rate start, loss rate end)
        # value: float. percent_fraction for that loss rate
        self.dist_pdf = {}

        curr_val = 0
        for bucket in json_dict['distribution']:
            new_val = bucket['percent_fraction']
            if curr_val == 0:
                val_range_start = curr_val
            else:
                val_range_start = round(curr_val + PERCENT_FRACTION_GRANULARITY, FRACTION_DECIMAL_PLACES)
            val_range_end = round(curr_val + new_val, FRACTION_DECIMAL_PLACES)
            val_range = (val_range_start, val_range_end)
            loss_rate_bucket = (bucket['start'], bucket['end'])
            self.dist_dict[val_range] = loss_rate_bucket
            self.dist_pdf[loss_rate_bucket] = new_val
            # update curr_val for the next range
            curr_val = val_range_end

    def generate(self) -> float:
        """ 
        Generates a loss rate as per the loaded distribution
        """
        # Generate a random number between 0 and 100
        rand_number = random.uniform(0, 100) # 0 to 100 percent

        # Round it to 2 decimal places
        rand_number = round(rand_number, 2)

        # check the dist dict key (val ranges) in which the number falls
        rand_num_val_range = None
        for val_range in self.dist_dict:
            val_range_start = val_range[0]
            val_range_end = val_range[1]
            if val_range_start <= rand_number  and rand_number <= val_range_end:
                rand_num_val_range = val_range
                break
        
        assert rand_num_val_range != None, "generated rand number MUST fall in one of the ranges"
        
        # from the chosen loss rate bucket, return a random loss rate
        loss_rate_bucket = self.dist_dict[rand_num_val_range]
        loss_rate_start = loss_rate_bucket[0]
        loss_rate_end   = loss_rate_bucket[1]

        return random.uniform(loss_rate_start, loss_rate_end)

    def test(self, num_trials: int) -> None:
        """ 
        Function to test if the generated loss rates result into the
        input distribution. Prints the test results.

        Argument:
            num_trials: int. Number of trials to run.
        """
        output_dist_counts = {}

        # initialize the counts to zero
        for loss_rate_bucket in self.dist_pdf:
            output_dist_counts[loss_rate_bucket] = 0

        # start running the trials
        for i in range(num_trials):
            loss_rate = self.generate()
            
            # check which loss rate bucket the count belongs to
            member_loss_rate_bucket = None
            for loss_rate_bucket in self.dist_pdf:
                if loss_rate >= loss_rate_bucket[0] and loss_rate <= loss_rate_bucket[1]:
                    member_loss_rate_bucket = loss_rate_bucket
                    break

            assert member_loss_rate_bucket != None, "generated loss rate MUST belong to one of the buckets"
            
            # increment the count for that loss rate bucket
            output_dist_counts[member_loss_rate_bucket] += 1

        # compute the output distribution's PDF (in %)
        output_dist_pdf = {}
        for loss_rate_bucket in output_dist_counts:
            output_dist_pdf[loss_rate_bucket] = round(output_dist_counts[loss_rate_bucket] / num_trials * 100, FRACTION_DECIMAL_PLACES)

        # print the input and output PDF results side-by-side
        table = [["Loss Rate Bucket", "Input Fraction(%)", "Output Fraction(%)"]]

        for loss_rate_bucket in output_dist_pdf:
            loss_rate_bucket_string = "[{}, {}]".format(loss_rate_bucket[0], loss_rate_bucket[1])
            row = [loss_rate_bucket_string, str(self.dist_pdf[loss_rate_bucket]), str(output_dist_pdf[loss_rate_bucket])]
            table.append(row)

        print(tabulate.tabulate(table))

