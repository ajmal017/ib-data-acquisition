def f1(self):
    print(self.someAttr)

class someWrapper:
    def __init__(self):
        self.someAttr = "hello world"

    def someMethod(self):
        f1(self)

if __name__=="__main__":
    x = someWrapper()
    x.someMethod()