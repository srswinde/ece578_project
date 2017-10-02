#!/usr/bin/python3

from threading import Thread, Lock
from queue import Queue, Empty
import time
import random
import math
from counters import count_down, Counter
import copy

# time in micro seconds
SLOT = 20
SIFS = 10
DIFS = 40



# data size in bytes
FRAME = 1500
RTS = 30
CTS = 30
ACK = 30

TX_RATE = 6e6 #mbs
DATA_TX_TIME = FRAME*8/TX_RATE

CW = 4
CW_MAX = 1024

MAX_COUNT = 5000

FRAME_TX_TIME = FRAME

class Station( Thread ):
    """The nodes of the network"""
    running = False
    def __init__( self, medium, name ):
        super().__init__()
        self.medium = medium
        self.name = name
        self.receiver = Connection()
        self.sender = Connection( self )
        self.status = None
        self.ack = None
        self.ack_transmit = False
        self.back_off = 0
        self.back_off_multiplier = 1
        self.back_off_countdown = count_down(CW, "Sation {} Back Off".format(name), self.transmit)
        self.medium.register( self )

    def run( self ):
        self.running = True
        
        while self.running:
            time.sleep(0.01)
            if self.medium.idle:
                #make sure we are not frozen
                self.back_off_countdown.unfreeze()
            else:
                self.back_off_countdown.freeze()


            rx = self.recv()
            if rx:
                if rx.tx_type == "Frame":
                    self.ack = Ack( rx.receiver, rx.sender )
                elif rx.tx_type == "Ack":
                    pass
    def __repr__(self):
        return "<Station {}>".format(self.name)

    def recv( self ):
        try:
            tx = self.receiver.get( block=False )
        except Empty:
            tx = None
        if tx is not None:
            if tx.receiver is not self.name:
                #its not for us throw it away
                tx = None

        return tx

    def send(self, station):
        # put the frame in the send queue
        self.sender.put( Frame( self.name, station ), False )


    def kill(self):
        self.running = False

    def transmit(self):
        print("trying to transmit frame")
        self.sender.transmit = True

    def DIFS_trigger(self):
        if not self.sender.empty():
            back_off = random.randint( 0, CW*self.back_off_multiplier )*SLOT
            self.back_off_countdown.start( back_off )


    def SIFS_trigger(self):
        if self.ack:
            self.ack_transmit = True


class Medium( Thread ):
    """The shared medium inherits from Thread
    this will watch over the communication
    channel and simulate the collisions or 
    successfull transmissions
    """

    running = False

    def __init__(self):

        super().__init__()
        self.stations = None

        self.DIFS_countdown = count_down( DIFS, "DIFS", self.DIFS_trigger )
        self.SIFS_countdown = count_down( SIFS, "SIFS", self.SIFS_trigger )
        self.Traverse_countdown = count_down(10, "TRAVERSE")

        self.counter= Counter( 5000, self.DIFS_countdown, self.SIFS_countdown, self.Traverse_countdown )

        self.idle = False


    def DIFS_trigger(self):
        if self.stations:
            for st in self.stations:
                st.DIFS_trigger()

    def SIFS_trigger( self ):
        if self.stations:
            for st in self.stations:
                st.SIFS_trigger()

    def register( self, station ):
        """Each station should register with the common medium
        so the medium can handle its data traffic."""
        if self.stations is None:
            self.stations = []

        self.counter.register( station.back_off_countdown )
        self.stations.append( station )


    def run(self):
        """Most of the important timekeeping etc is done here.
        In the while self.running block. Each loop is 
        1 micro second and will count down the various
        timers before handling the transmission
        """

        self.running = True
        first_loop = True
        for count in self.counter:
            time.sleep(0.01)

            if count == None:
                break

            if self.counter.first_loop:
                self.DIFS_countdown.start()
                
            


            if self.stations is None:
                    #Nobdody has registered
                    
                    continue

            if self.DIFS_countdown: # In Difs state
                self.idle = False
                continue

            elif self.SIFS_countdown: # In SIFS state
                self.idle = False
                continue

            elif self.Traverse_countdown: # Waiting for tx to traverse medium
                self.idle = False
                #we don't continue here because we want to look for collisions
        
            else:
                self.idle = True
                
            communication_tally = []
            for station in self.stations:
                try:
                    tx = station.sender.get(block = False)
                except Empty:
                    tx = None

                
        
                communication_tally.append(tx)

            if len( communication_tally ) > 1:
                print("We have a collision, same back off")
                pass
            elif self.Traverse_countdown:
                print("We have a collision")
                
            else:
                self.traverse_medium(tx)
            

            


    def traverse_medium( self, frm ):
        tx_time_s = frm.size*8/TX_RATE 
        tx_time_microseconds = tx_time_s*1e6


        self.Traverse_countdown.start( tx_time_microseconds, self.connect_the_pipe, frm )

    def connect_the_pipe(self, frm):
        for station in self.stations:

            station['rx'].put(frm)

    def kill(self):
        self.running = False
        self.counter.kill()




class Connection(Queue):
    """Connection class inherits from queue.
    Here we can overwrite the methods
    put and get. this will give us access
    to the receiving and transmitting. 
    """


    def __init__(self, owner=None ):
        self.owner = owner
        if self.owner:
            self.transmit = True
        else:
            self.transmit = False
        super().__init__()

    def get( self, *args, **kwargs ):
        """Overwrite the get part of the queue
        Here we check to see if there is an ack
        waiting for transmission. If so we transmit
        to the medium. If not we check for a 
        a data frame waiting to be transmitted. 
        The data frame and ack tranmissions are 
        triggered by the DIFS and SIFS trigger 
        function respectively"""
        if self.owner:
            if self.owner.ack_transmit:
            
                resp = copy.deepcopy( self.owner.ack )
                self.owner.ack = None
                self.owner.ack_transmit = False
            

            if self.transmit:
                return super().get( *args, **kwargs )
                self.transmit = False
            else:
                raise Empty
        else:
            return super().get( *args, **kwargs )


    def put( self, msg, *args, **kwargs ):
        super().put( msg, *args, **kwargs )

    


class Transmission():
    """Place holder for anything that 
    is methods and members common to 
    acks and frames"""
    def __init__( self, sender, receiver ):
        self.sender = sender # address or name of sender.
        self.receiver = receiver #address or name of receiver.

    def __repr__(self):
        return "<Frame sender: {} recver: {}>".format(self.sender, self.receiver)



class Ack(Transmission):
    tx_type = "Ack"
    size = 30

class Frame(Transmission):
    tx_type = "Frame"
    size = 1500

class RTS(Transmission):
    pass

class CTS(Transmission):
    pass

def poisson_distribution(Lambda=1, n=5):
    X = set() # set is handy for probability distributions

    for ITER in range(n):
        u = random.random() # random number between 0  and 1
        X.add((-1/Lambda)*math.ln(1-u))
        
    return X




def main():
    
    shared_medium = Medium()
    A = Station( shared_medium, 'A' )
    B = Station( shared_medium, 'B' )
    C = Station( shared_medium, 'C' )
    D = Station( shared_medium, 'D' )
    
    A.start()
    B.start()
    C.start()
    D.start()
    shared_medium.start()
    print("Attempting to send")
    A.send("B")
    C.send("D")
    time.sleep(1)   

    A.kill()
    A.join()

    B.kill()
    B.join()

    C.kill()
    C.join()

    D.kill()
    D.join()

    shared_medium.kill()
    shared_medium.join()


main()
