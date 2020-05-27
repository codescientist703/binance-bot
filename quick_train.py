import logging
import coloredlogs
import sys 


from trading_bot.agent import Agent
from trading_bot.methods import train_model, evaluate_model
from trading_bot.utils import (
	get_stock_data,
	format_currency,
	format_position,
	show_train_result,
	switch_k_backend_device
)
def main(train_stock, window_size, batch_size, ep_count,
		 strategy="t-dqn", model_name="model_debug", pretrained=False,
		 debug=False):
 
	agent = Agent(window_size, strategy=strategy, pretrained=pretrained, model_name=model_name)
	
	train_data = get_stock_data(train_stock)

	for episode in range(1, ep_count + 1):
		train_result = train_model(agent, episode, train_data, ep_count=ep_count,
								   batch_size=batch_size, window_size=window_size)

if __name__ == "__main__":

	train_stock = sys.argv[1]
	training_stock = 'training_data/' + train_stock + '.csv'
	strategy = 'double-dqn'
	window_size = 10
	batch_size = 32
	ep_count = 10
	model_name = 'model_double-dqn_GOOG_50'
	pretrained = False
	debug = True

	coloredlogs.install(level="DEBUG")
	switch_k_backend_device()
	print(training_stock)
	
	try:
		main(training_stock, window_size, batch_size,
			 ep_count, strategy=strategy, model_name=model_name, 
			 pretrained=pretrained, debug=debug)
	except KeyboardInterrupt:
		print("Aborted!")
