from __future__ import print_function
import configparser
from telegram.ext import Updater
import logging
from telegram.ext import CommandHandler
import time
import datetime
import json

from functools import wraps
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
#from apiclient import discovery
from google.oauth2 import service_account

class BuuttiBot:

    chat_ids = []
    LIST_OF_ADMINS = []
    LIST_OF_WAITING_ADMINS = {}

    def __init__(self, config):
        self.config = config
        self.chat_ids = json.loads(config.get("BOT","chat_ids"))
        self.LIST_OF_ADMINS = json.loads(config.get("BOT", "admin"))
        self.LIST_OF_WAITING_ADMINS = json.loads(config.get("BOT", "waitingadmin").replace("\'", "\""))
        self.updater = Updater(token=config["BOT"]["apiToken"], use_context=True)
        disp = self.updater.dispatcher
        self.jobs = self.updater.job_queue

        start_handler = CommandHandler('start', self.start)
        disp.add_handler(start_handler)

        register_handler = CommandHandler("register", self.registerChannel)
        disp.add_handler(register_handler)

        date_handler = CommandHandler("date", self.kavijatCustom, pass_args=True)
        disp.add_handler(date_handler)

        makeAdmin_handlere = CommandHandler("giveadmin", self.makeMeAdmin)
        disp.add_handler(makeAdmin_handlere)

        show_handler = CommandHandler("show", self.showWaiting)
        disp.add_handler(show_handler)

        approval_handle = CommandHandler("approve", self.approve, pass_args=True)
        disp.add_handler(approval_handle)

        self.updater.start_polling()
        runTime = json.loads(config.get("BOT","runTime"))
        operationTime = datetime.time(runTime[0],
                        runTime[1],
                        runTime[2])
        daysRun = json.loads(config.get("BOT", "runDays"))
        self.google = GoogleSheet(config)
        self.dailyNotification = self.jobs.run_daily(self.kavijat, operationTime, days=tuple(daysRun))


    def restricted(func):
        @wraps(func)
        def wrapped(self, update, context, *args, **kwargs):
            user_id = update.effective_user.id
            if user_id not in self.LIST_OF_ADMINS:
                print("Unauthorized access denied for {}.".format(user_id))
                context.bot.send_message(chat_id=update.message.chat_id, text=
                "Unauthorized! Access denied!")
                return
            else:
                print("authorized")
            return func(self, update, context, *args, **kwargs)
        return wrapped

    def start(self, update, context):
            context.bot.send_message(chat_id=update.message.chat_id, text="Hello world")

    @restricted
    def registerChannel(self, update, context):
        if update.message.chat_id not in self.chat_ids:
            self.chat_ids.append(update.message.chat_id)
            print("New channel registered")
            self.config.set("BOT", "chat_ids", str(self.chat_ids))
            with open("config.ini", "w+") as configfile:
                self.config.write(configfile)
            context.bot.send_message(chat_id=update.message.chat_id, text="Channel registered for daily updates")
        else:
            context.bot.send_message(chat_id=update.message.chat_id, text="Channel already registered")

    @restricted
    def showWaiting(self, update, context):
        result = ""
        for key in self.LIST_OF_WAITING_ADMINS.keys():
            line = "{}: {}\n".format(self.LIST_OF_WAITING_ADMINS[key], key)
            result += line
        if result == "":
            result = "No waiting admins requests"
        context.bot.send_message(chat_id=update.message.chat_id, text=result)

    @restricted
    def approve(self, update, context):
        args = context.args
        if len(args) != 1:
            context.bot.send_message(chat_id=update.message.chat_id, text="wrong amount of arguments")
        else:
            try:
                args = args[0]
                if args in self.LIST_OF_WAITING_ADMINS.keys() and \
                    int(args) not in self.LIST_OF_ADMINS:
                    self.LIST_OF_ADMINS.append(int(args))
                    self.config.set("BOT", "admin", str(self.LIST_OF_ADMINS))
                    del self.LIST_OF_WAITING_ADMINS[args]
                    self.config.set("BOT", "waitingadmin", str(self.LIST_OF_WAITING_ADMINS))
                    with open("config.ini", "w+") as configfile:
                        self.config.write(configfile)
                    context.bot.send_message(chat_id=update.message.chat_id, text="User approved to be admin")
                elif args not in self.LIST_OF_WAITING_ADMINS.keys():
                    context.bot.send_message(chat_id=update.message.chat_id, text="No such id waiting for approval")
            except:
                print("error")

    def makeMeAdmin(self, update, context):
        print(update.message.from_user.first_name)
        if update.effective_user.id not in self.LIST_OF_WAITING_ADMINS.values() and \
            update.effective_user.id not in self.LIST_OF_ADMINS:
            first_name = update.message.from_user.first_name
            self.LIST_OF_WAITING_ADMINS[str(update.effective_user.id)] = first_name
            self.config.set("BOT", "waitingadmin", str(self.LIST_OF_WAITING_ADMINS))
            with open("config.ini", "w+") as configfile:
                self.config.write(configfile)
            context.bot.send_message(chat_id=update.message.chat_id, text="Your request is waiting for approval")
        elif update.effective_user.id in self.LIST_OF_WAITING_ADMINS.values():
            context.bot.send_message(chat_id=update.message.chat_id, text="You have already sent a request")
        elif update.effective_user.id in self.LIST_OF_ADMINS:
            context.bot.send_message(chat_id=update.message.chat_id, text="You are already admin")

    def kavijat(self, context):
        result = self.getAllKavijat(datetime.datetime.today())

        for id in self.chat_ids:
            context.bot.send_message(chat_id=id, text=result)

    def getAllKavijat(self, queryDate):
        result1 = self.google.getDayVisitorsProg(queryDate)
        result2 = self.google.getDayVisitorsRobots(queryDate)
        result3 = self.google.getDayVisitorsKKProg(queryDate)
        result4 = self.google.getDayVisitorsKKRobots(queryDate)
        date = queryDate.day
        month = queryDate.month
        result = "{}.{}.\n".format(date, month)
        if result1 != 'No data found.' and result1 != "No data on requested day":
            result += result1
            result += "\n"
        if result2 != 'No data found.' and result2 != "No data on requested day":
            result += result2
            result += "\n"
        if result3 != 'No data found.' and result3 != "No data on requested day":
            result += result3
            result += "\n"
        if result4 != 'No data found.' and result4 != "No data on requested day":
            result += result4
        if result == "{}.{}.\n".format(date, month):
            result = result1
        return result

    def kavijatCustom(self, update, context):
        args = context.args
        if update.message.chat_id not in self.chat_ids:
            result = "This channel is not authorized"
        else:
            if len(args) != 1:
                result = "Too many arguments"
            else:
                args = args[0].split(".")
                if len(args) != 3:
                    print("args not 3")
                    result = "Day needs to be in %d.%m."
                else:
                    try:
                        search = datetime.datetime.today()
                        search = search.replace(day=int(args[0]), month=int(args[1]))
                    except:
                        print("not int")
                        print(args)
                        result = "Day needs to be in %d.%m."
                    else:
                        result = self.getAllKavijat(search)

        context.bot.send_message(chat_id=update.message.chat_id, text=result)

    def idle(self):
        self.updater.idle()

class GoogleSheet:

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    SPREADSHEET_PROGRAMMING_ID = ""
    SPREADSHEET_ROBOTICS_ID = ""
    SPREADSHEET_KK_PROGRAMMING_ID = ""
    SPREADSHEET_KK_ROBOTICS_ID = ""
    RANGE_NAME1 = ""
    RANGE_NAME2 = ""
    RANGE_NAME3 = ""
    RANGE_NAME4 = ""

    def __init__(self, config):
        self.SPREADSHEET_PROGRAMMING_ID = config["Google"]["spreadsheetidProgramming"]
        self.RANGE_NAME1 = config["Google"]["sheetRange1"]
        self.SPREADSHEET_ROBOTICS_ID = config["Google"]["spreadsheetidRobotics"]
        self.RANGE_NAME2 = config["Google"]["sheetRange2"]

        self.SPREADSHEET_KK_PROGRAMMING_ID = config["Google"]["spreadsheetidkkProg"]
        self.RANGE_NAME3 = config["Google"]["sheetRange3"]
        self.SPREADSHEET_KK_ROBOTICS_ID = config["Google"]["spreadsheetidkkRob"]
        self.RANGE_NAME4 = config["Google"]["sheetRange4"]

        creds = None
        try:
            #secret_file = os.path.join(os.getcwd(), "BuuttiBot-7aa2ada2a5e9.json")
            creds = service_account.Credentials.from_service_account_file("BuuttiBot-7aa2ada2a5e9.json", scopes=self.SCOPES)
            service = build('sheets', 'v4', credentials=creds)
        except OSError as e:
            print(e)
        # Call the Sheets API
        self.sheet = service.spreadsheets()

    def getDayVisitorsProg(self, requestDay):
        print("fetching data")
        result = self.sheet.values().get(spreadsheetId=self.SPREADSHEET_PROGRAMMING_ID,
                                    range=self.RANGE_NAME1).execute()
        values = result.get('values', [])

        if not values:
            return 'No data found.'
        else:
            days = values[7]
            current = 0
            date = requestDay.day
            month = requestDay.month
            for i, day in enumerate(days):
                day = day.split(".")
                try:
                    dateSheet = int(day[0])
                    monthSheet = int(day[1])
                except:
                    continue
                if dateSheet == date and monthSheet == month:
                    current = i
            if current == 0:
                print("no data")
                return "No data on requested day"
            else:
                returnString = ""
                for x in range(0, 7):
                    returnString += values[x][0]
                    returnString += " "
                    returnString += values[x][current]
                    returnString += "\n"
                print(returnString)
                return returnString

    def getDayVisitorsKKProg(self, requestDay):
        result = self.sheet.values().get(spreadsheetId=self.SPREADSHEET_KK_PROGRAMMING_ID,
                                    range=self.RANGE_NAME3).execute()
        values = result.get('values', [])

        if not values:
            return 'No data found.'
        else:
            days = values[5]
            current = 0
            date = requestDay.day
            month = requestDay.month
            for i, day in enumerate(days):
                day = day.split(".")
                try:
                    dateSheet = int(day[0])
                    monthSheet = int(day[1])
                except:
                    continue
                if dateSheet == date and monthSheet == month:
                    current = i
            if current == 0:
                print("no data")
                return "No data on requested day"
            else:
                returnString = "KoodiKärpät:\n"
                for x in range(0, 5):
                    returnString += values[x][0]
                    returnString += " "
                    returnString += values[x][current]
                    returnString += "\n"
                print(returnString)
                return returnString


    def getDayVisitorsRobots(self, requestDay):
        result = self.sheet.values().get(spreadsheetId=self.SPREADSHEET_ROBOTICS_ID,
                                        range=self.RANGE_NAME2).execute()
        print("fetching data")
        values = result.get('values', [])

        if not values:
            return 'No data found.'
        else:
            days = values[1]
            current = 0
            date = requestDay.day
            month = requestDay.month
            for i, day in enumerate(days):
                day = day.split(".")
                try:
                    dateSheet = int(day[0])
                    monthSheet = int(day[1])
                except:
                    continue
                if dateSheet == date and monthSheet == month:
                    current = i
            if current == 0:
                print("no data")
                return "No data on requested day"
            else:
                returnString = ""
                returnString += "Robotti kerho \n"
                returnString += values[0][current]
                returnString += "\n"
                print(returnString)
                return returnString

    def getDayVisitorsKKRobots(self, requestDay):
        result = self.sheet.values().get(spreadsheetId=self.SPREADSHEET_KK_ROBOTICS_ID,
                                        range=self.RANGE_NAME4).execute()
        values = result.get('values', [])

        if not values:
            return 'No data found.'
        else:
            days = values[1]
            current = 0
            date = requestDay.day
            month = requestDay.month
            for i, day in enumerate(days):
                day = day.split(".")
                try:
                    dateSheet = int(day[0])
                    monthSheet = int(day[1])
                except:
                    continue
                if dateSheet == date and monthSheet == month:
                    current = i
            if current == 0:
                print("no data")
                return "No data on requested day"
            else:
                returnString = ""
                returnString += "Robotti kerho KK\n"
                returnString += values[0][current]
                returnString += "\n"
                return returnString



config = configparser.ConfigParser()
config.read("config.ini")


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

bot = BuuttiBot(config)
print("bot started")
bot.idle()
#gogle = GoogleSheet(config)
#print(gogle.getDayVisitorsRobots(datetime.datetime(2019, 1, 22)))
