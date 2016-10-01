# AlgoTrade-IB
This is an adaptaion of python pyalgo
To do:
The queue that link broker, and strategy.

The IBroker connects to Interactive broker and manage sending/receiving commands
the my strategy needs a Ibroker to lanch and receive command to IB
the my strategy can also works with historical data for back testing

Prerequesite
Requires:
- ibPy - https://github.com/blampe/IbPy included in the OneDrive Directory or download the zip file, unzip it, enter into the IbPy-Master and run : python setup.py install from the anaconda command prompt
- trader work station or IB Gateway - https://www.interactivebrokers.com/en/?f=%2Fen%2Fsoftware%2Fibapi.php&ns=T
- PyAlgo 2.7 included in the onedrive python bin directory or pip install pyalgotrade on Anaconda commmand prompt
- Elastic Search for storing and visualizing performances - Not mandatory
File Structure

MyAlgoSystem

   |- lib
   
        |- ElasticSearch 
        
   |- control_files
   
        |- runfile : File with just START, STOP that controls liveExec
        
        |- run_number : File with a number to uniquely identify strategy run in ElasticSearch
        
   |- output contains a sqlite database with all the strategy orders & position current and historical value
   
             contains csv file with strategy current orders & position and historical value for running strategy   
             
    
The IBroker as a queue where commands are executed
The Datafeed as a queue where price informations are pushed to the strategy
The strategy as both a datafeed to get price for the strategy and IbBroker to send orders to be executed

