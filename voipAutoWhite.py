#!/usr/bin/python
import requests
import re
import datetime
import sys
import getopt

restAddress = 'https://voip.ms/api/v1/rest.php'
apiUserName = None
apiPassword = None
minDuration = '00:00:10'
myPhoneNumber = None
callerIdFoundRE = re.compile(r'"([^"]+)" <(\d*)>$')
callerIdNoName = re.compile(r'\d*$')
autoWhiteGroupName = 'auto_white'

def usage():
    print('voipAutoWhite.py -u <username> -p <password> -m <phonenumber>')
    sys.exit()

def getParameters(argv):
    global apiUserName, apiPassword, myPhoneNumber
    try:
        opts, args = getopt.getopt(argv, "hu:p:m:", ["username=", "password=", "phonenumber="])
        for opt, arg in opts:
            if opt == '-h':
                usage()
            elif opt in ('-u', '--username'):
                apiUserName = arg
            elif opt in ('-p', '--password'):
                apiPassword = arg
            elif opt in ('-m', '--phonenumber'):
                myPhoneNumber = arg
    except:
        usage()
            

def isValidName(name):
    if len(name) < 3 or name.startswith('UNKNOWN'):
        return False
    if name.startswith(' ', -3):
        return false # probably city and state
    return True

def isValidNumber(number):
    return len(number) >= 10 and callerIdNoName.match(number)

def getCDRs():
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    params = {
        'method':'getCDR',
        'api_username': apiUserName, 'api_password': apiPassword,
        'date_from':str(yesterday), 'date_to':str(tomorrow), 'timezone':'-7',
        'answered':'1'
    }
    r = requests.get(restAddress, params=params)
    response = r.json()
    status = response['status']
    if status != 'success':
        return []
    result = []
    cdrs = response['cdr']
    for cdr in cdrs:
        destination = cdr['destination']
        if destination == myPhoneNumber:
            if cdr['duration'] >= minDuration:
                callerId = cdr['callerid']
                match = callerIdFoundRE.match(callerId)
                if match:
                    #print('found', callerId, match.group(1))
                    name = match.group(1)
                    number = match.group(2)
                    if isValidNumber(number):
                        if isValidName(name):
                            result.append([ number, name])
                        else:
                            result.append([number, None])
                elif isValidNumber(callerId):
                    result.append([ callerId, None])
                elif isValidNumber(destination):
                    result.append(destination, None)        
    return result

def getPhonebookNumbers():
    params = {
        'method':'getPhonebook',
        'api_username': apiUserName, 'api_password': apiPassword
    }
    r = requests.get(restAddress, params=params)
    response = r.json()
    status = response['status']
    if status != 'success':
        print('unable to get phonebook')
        exit(-1)
    result = set()
    for phonebook in response['phonebooks']:
        result.add(phonebook['number'])
    return result

def getExistingAutoWhiteGroup():
    params = {
        'method':'getPhonebookGroups',
        'api_username': apiUserName, 'api_password': apiPassword,
        'name' : autoWhiteGroupName
    }
    r = requests.get(restAddress, params=params)
    response = r.json()
    if response['status'] != 'success':
        return None
    for group in response['phonebook_groups']:
        if group['name'] == autoWhiteGroupName:
            return group['phonebook_group']
    return None # Can this happen?

def defineAutoWhiteGroup():
    params = {
        'method':'setPhonebookGroup',
        'api_username': apiUserName, 'api_password': apiPassword,
        'name' : autoWhiteGroupName
    }
    r = requests.get(restAddress, params=params)
    response = r.json()
    return response['status'] == 'success';
    
def getAutoWhiteGroup():
    group = getExistingAutoWhiteGroup()
    if group is not None:
        return group
    defineAutoWhiteGroup()
    return getExistingAutoWhiteGroup()

def addPhonebookEntry(name, number, group):
    params = {
        'method':'setPhonebook',
        'api_username': apiUserName, 'api_password': apiPassword,
        'name' : name,
        'number' : number,
        'group' : group
    }
    r = requests.get(restAddress, params=params)
    response = r.json()
    return response['status'] == 'success';
    
def updatePhonebook(cdrs):
    phonebookNumbers = getPhonebookNumbers()
    autoWhiteGoup = None
    for cdr in cdrs:
        number = cdr[0]
        if not number in phonebookNumbers:
            phonebookNumbers.add(number)
            if autoWhiteGoup is None:
                autoWhiteGoup = getAutoWhiteGroup()
            name = cdr[1]
            if name is None:
                name = number
            if not addPhonebookEntry(name, number, autoWhiteGoup):
                print('update phone failed', name, number, autoWhiteGoup)
                exit(-1)

getParameters(sys.argv[1:])
if apiUserName is None or apiPassword is None or myPhoneNumber is None:
    usage()
updatePhonebook(getCDRs())
