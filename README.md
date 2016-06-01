# AlgoTrade-IB
This is an adaptaion of python pyalgo
To do:
The queue that link broker, and strategy.

The IBroker connects to Interactive broker and manage sending/receiving commands
the my strategy needs a Ibroker to lanch and receive command to IB
the my strategy can also works with historical data for back testing

Prerequesite
PyAlgo 2.7

The IBroker as a queue where commands are executed
The Datafeed as a queue where price informations are received
The strategy as both a datafeed to get price for the strategy and IbBroker to send orders to be executed

