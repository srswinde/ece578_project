#!/usr/bin/python3


class count_down:

    def __init__ (self, top=None, name="no name", trigger_function=lambda :print("Ring RING!!"), *args ):
        self.top = top
        self.count = self.top
        self.fxn = trigger_function
        self.args = args
        self.name = name
        self.timing = False
        self.frozen = False

    def __call__(self):
        
        if self.timing:
            if self.count == 0:
                #edge detection: we changed from 1 to 0
                self.timing = False
                self.fxn( *self.args )

            else:
                if not self.frozen:
                    self.count -= 1

        return self.count


    def cancel(self):
        self.timing = 0
        self.count  = self.top
    def __bool__( self ):
        return self.timing

    def start( self, top=None, fxn=None, *args ):
        if top:
            self.top = top
        if self.top == None:
            raise ValueError("Need to set top of timer")
        
        if fxn:
           self.fxn = fxn
           self.args = args

        self.count = self.top
        self.timing = True

    def freeze( self ):
        if not self.frozen:
            self.frozen = True
        
    def unfreeze( self ):
        if self.frozen:
            self.frozen = False

    def __repr__( self ):
        return "<count_down:{} counter:{} timing:{} frozen:{}>".format(self.name, self.count, self.timing, self.frozen)

    def __int__(self):
        return self.count

    def __gt__(self, val):
        
        if self.count > val:
            return True
        else:
            return False

    def __lt__(self, val):
        if self.timing:
            True
        if self.count < val:
            return True
        else:
            return False



class Counter:

    def __init__(self, max_count, *registrants):
        self.max_count = max_count
        self.count = -1
        self.counting = True
        self.count_downers = []
        self.first_loop = True

        if registrants:
            self.count_downers.extend(registrants)
        
    def register(self, cntdwn ):
       self.count_downers.append( cntdwn )

    def __iter__(self):
        

        while self.counting:

            if self.count == 0:
                self.first_loop = False

            self.count+= 1
            self.count%= self.max_count


            for cntdwner in self.count_downers:
                #print( cntdwner )
                cntdwner()
                #if cntdwner: print( "\t", cntdwner )
                #else: print("\t", cntdwner)
                cntdwner()
            yield self.count

    def kill(self):
        self.counting = False


    def idle_stuff(self):
        pass

    def __repr__(self):
        return "{} micro seconds".format(self.count)

        


def main():
    c=Counter()
    cd = count_down(20)
    cd.start()
    c.register(cd)
    for a in c:
        pass
