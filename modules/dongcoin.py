# Implements dongcoins and buttcoins to make bets and place bounties.

from peewee import peewee
import urllib.request
import urllib.parse
import json
import http.server
import _thread
import http.cookiejar

dongerdong = None

originalwin = None

originalprerules = None

cookiejar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

# buttcoin transaction stuff
def getToken(tType):
    print("Token {0}".format(tType))
    r = opener.open("https://buttcoin.us/api.php?action=token&type={1}&key={0}&human=nope".format(dongerdong.config['privkey'], tType)).read().decode()
    token = json.loads(r)
    print(r)
    if token['result'] == "success":
        return token['token']
    else:
        return False
        
def transfer(to, amount, message):
    return opener.open("https://buttcoin.us/api.php?action=transfer&token={0}&amount={1}&message={2}&account={3}".format(getToken("transfer"), amount, urllib.parse.quote_plus(message), to)).read().decode()


# Function called on !deposit (to exchange buttcoins for dongcoins)
def deposit(dong, cli, ev):
    if len(ev.splitd) < 2:
        cli.privmsg(ev.target, "Usage: !deposit <amount of buttcoins>")
        return
    
    try:
        if int(ev.splitd[1]) <= 0:
            raise
    except:
        cli.privmsg(ev.target, "Usage: !deposit <amount of buttcoins>")
        return
    print("foo")
    
    ev.splitd[1] = str(int(ev.splitd[1]) + 1) # ayy lmao

    r = urllib.request.urlopen("https://hira.io/butt.php?a=new&amount=" + ev.splitd[1] + "&callback=" + urllib.parse.quote_plus(dong.config['localserver']) + "&deposit_to=" + dong.config['deposit-to']).read()
    print("bar")
    stuff = json.loads(r.decode('utf-8'))
    
    ButtCoinPending.create(account=cli.channels[ev.target.lower()].users[ev.source.lower()].account,
                            secret=stuff['secret'], tid=stuff['id'], amount=(int(ev.splitd[1]) - 1))
    cli.privmsg(ev.target, "Pay here ({1} buttcoins): https://hira.io/buttwait.php?tid={0}".format(stuff['id'], stuff['amount']))

# Called from the HTTP server when a transaction is finished
def paid(pid):
    # Step 2: the user paid, announce that and give em' their monies
    stuff = urllib.parse.parse_qs(pid)
    sid = stuff['secret'][0]
    trid = stuff['id'][0]
    
    try:
        transaction = ButtCoinPending.get(ButtCoinPending.secret == sid)
        if not transaction:
            raise
    except:
        print("DA FOCK?!")
        return
    
    try:
        credi = Balances.get(Balances.account == transaction.account)
        if not credi:
            raise
        credi.balance += transaction.amount * 100
        credi.save()
    except:
        credi = Balances.create(account = transaction.account, balance = transaction.amount * 100)

# !balance command, to check your own balance.
def balance(dong, cli, ev):
    try:
        credi = Balances.get(Balances.account == cli.channels[ev.target.lower()].users[ev.source.lower()].account)
        if not credi:
            raise
    except:
        credi = Balances.create(account = cli.channels[ev.target.lower()].users[ev.source.lower()].account, balance = 0)
        
    cli.privmsg(ev.target, "\002{0}\002's balance: \002{1}\002 dongcoins (\002{2}\002 buttcoins)".format(cli.channels[ev.target.lower()].users[ev.source.lower()].account,
                credi.balance, round((credi.balance/100), 2)))

# !cashout command, to convert your dongcoins into buttcoins.
def cashout(dong, cli, ev):
    if len(ev.splitd) < 2:
        cli.privmsg(ev.target, "Usage: !cashout <amount of buttcoins>")
        return
    
    try:
        if int(ev.splitd[1]) <= 0:
            raise
    except:
        cli.privmsg(ev.target, "Usage: !cashout <amount of buttcoins>")
        return
    
    if int(ev.splitd[1]) < 5:
        cli.privmsg(ev.target, "The minimum cashout is of 5 buttcoins")
        return
    
    try:
        credi = Balances.get(Balances.account == cli.channels[ev.target.lower()].users[ev.source.lower()].account)
        if not credi:
            raise
    except:
        credi = Balances.create(account = cli.channels[ev.target.lower()].users[ev.source.lower()].account, balance = 0)
    
    if (credi.balance /100) < int(ev.splitd[1]):
        cli.privmsg(ev.target, "You don't have enough buttcoins to do that!")
        return
    
    res = transfer(ev.source.lower(), ev.splitd[1], "cashout")
    
    res = json.loads(res)
    
    if res['result'] == "success":
        cli.privmsg(ev.target, "Done!")
        credi.balance = credi.balance - (int(ev.splitd[1]) * 100)
        credi.save()
    elif res['result'] == "error":
        if res['message'] == "balance":
            cli.privmsg(ev.target, "Error: I don't have enough balance to do that :(")
        elif res['message'] == "account-wtf":
            cli.privmsg(ev.target, "You don't have an account on the buttcoin central bank!")
        else:
            cli.privmsg(ev.target, "zomg, weird error!")
            

# create database tables and stuff

database = peewee.SqliteDatabase('dongerdong.db')
database.connect()

class BaseModel(peewee.Model):
    class Meta:
        database = database

# NEW Stats table
class Balances(BaseModel):
    account = peewee.CharField()
    balance = peewee.IntegerField()

class ButtCoinPending(BaseModel):
    tid = peewee.CharField()  # Transaction ID
    account = peewee.CharField() # user account
    secret = peewee.CharField() # Transaction secret
    amount = peewee.IntegerField()

# Mini HTTP server to verify transactions
class buttServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(self.path)
        if self.path.startswith("/buttpay"):
            paid(self.path.split("?")[1])
            self.wfile.write(b"HTTP/1.1 200 OK\n\n")

# we use this to track wins
def fakewin(winner, stats=True):
    global originalwin
    global dongerdong
    if dongerdong.deathmatch:
        plus = 10
    else:
        plus = 5
    
    if stats:
        try:
            credi = Balances.get(Balances.account == dongerdong.irc.channels[dongerdong.primarychan.lower()].users[winner.lower()].account)
            if not credi:
                raise
            credi.balance += plus
            credi.save()
        except:
            credi = Balances.create(account = dongerdong.irc.channels[dongerdong.primarychan.lower()].users[winner.lower()].account, balance = plus)
    
    originalwin(winner, stats)

def fakeprerules(self):
    global originalprerules
    global dongerdong

    if dongerdong.deathmatch:
        return

    return
    #cli.privmsg(ev.target, "Place your bets within next ten seconds! Syntax: !bet 5 <nickname>")

def bet(self):
    return


def loadModule(dong):
    global dongerdong
    global originalwin
    dongerdong = dong
    
    # Declare commands
    dong.extracommands['!deposit'] = deposit
    dong.extracommands['!balance'] = balance
    dong.extracommands['!cashout'] = cashout
    dong.extracommands['!bet'] = bet
    
    # Create tables
    Balances.create_table(True)
    ButtCoinPending.create_table(True)
    
    # Turn on the jet turbines
    httpd = http.server.HTTPServer(('', 8814), buttServer)
    _thread.start_new_thread(httpd.serve_forever, ())
    
    # launch th... override functions
    originalwin = dong.win
    dong.win = fakewin
