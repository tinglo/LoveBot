from flask import Flask
from flask import request
from snownlp import SnowNLP
from transitions import State
from transitions.extensions import GraphMachine as Machine
from machine import Bot
import time

import json

app = Flask(__name__)

VERIFY_TOKEN = 'YOUR_VERIFY_TOKEN'
PAGE_ACCESS_TOKEN = 'YOUR_PAGE_ACCESS_TOKEN'

## transition bot setting
emotion_upper_bound = 0.69 # good | normal | bad
emotion_lower_bound = 0.53
emotion_kind_list = ['good', 'normal', 'bad']

states=[ 
	{'name': 'initialSt', 'on_enter': ['first_meet']},
	{'name': 'greetingSt', 'on_enter': ['process_message']},
	{'name': 'peopleSt', 'on_enter': ['got_people']}, 
	{'name': 'eventSt', 'on_enter': ['got_event']}, 
	{'name': 'reasonSt', 'on_enter': ['got_reason']}, 
	{'name': 'replySt', 'on_enter': ['end_reply']}, 
]
transitions=[

	{'trigger': 'next_trans' , 'source': 'initialSt', 'dest': 'greetingSt', 'conditions': 'if_start'},
	{'trigger': 'next_trans' , 'source': ['initialSt','greetingSt'], 'dest': 'greetingSt', 'conditions': 'if_get_nothing' },
	{'trigger': 'next_trans' , 'source': 'greetingSt', 'dest': 'greetingSt', 'conditions': 'if_get_event_no_people' },

    {'trigger': 'next_trans', 'source': ['greetingSt', 'peopleSt'], 'dest': 'peopleSt', 'conditions': 'if_get_people_no_event'},

    {'trigger': 'next_trans', 'source': ['greetingSt', 'peopleSt', 'eventSt'], 'dest': 'eventSt', 'conditions': ['if_get_people','if_get_event']},
    
    {'trigger': 'next_trans', 'source': ['peopleSt', 'eventSt'], 'dest': 'reasonSt'},
    {'trigger': 'next_trans', 'source': 'reasonSt', 'dest': 'replySt'},
    {'trigger': 'next_trans', 'source': 'replySt', 'dest': 'replySt'},

    {'trigger': 'next_trans', 'source': 'replySt', 'dest': 'initialSt'}
]


love_bot = Bot(emotion_upper_bound, emotion_lower_bound, emotion_kind_list, PAGE_ACCESS_TOKEN)
machine = Machine(model = love_bot, states = states, transitions = transitions, initial = states[0]['name']) 


@app.route('/webhook', methods= ['GET'])
def set_webhook():
	if request.args.get('hub.verify_token') == VERIFY_TOKEN:
		return request.args.get('hub.challenge')

@app.route('/webhook', methods = ['POST'])
def handle_message():

	total_message = json.loads(request.data.decode('utf8'))['entry']
	bot_id, sender_id, real_text, user_text = analysis_message(total_message)

	if bot_id != sender_id and real_text == True:
		message_info = {
			'bot_id': bot_id,
			'sender_id': sender_id,
			'user_text': user_text
		}

		if love_bot.stuck_reply_count != 1:
			love_bot.next_trans(message_info)

		if love_bot.stuck_people_count == 1 and love_bot.people != '':

			love_bot.to_peopleSt(message_info)

		if love_bot.stuck_people_count == 0 and love_bot.people != '' and love_bot.reason == '':
			love_bot.to_eventSt(message_info)

		if love_bot.stuck_people_count == 0 and love_bot.people != '' and love_bot.reason != '' and love_bot.reply == '':
			love_bot.to_reasonSt(message_info)
		
		if love_bot.people != '' and love_bot.event != '' and love_bot.reason != '' and love_bot.reply != '':
			if love_bot.stuck_reply_count == 1:
				love_bot.to_replySt(message_info)
				love_bot.to_initialSt(message_info)


			else:
				love_bot.to_replySt(message_info)

	return

def analysis_message(total_message):
	bot_id = ''
	sender_id = ''
	real_text = False
	user_text = ''

	for entry in total_message:
		#print(total_message)
		if 'messaging' in entry:
			messagings = entry['messaging']
			bot_id = entry['id']

			for mes in messagings:
				sender_id = mes['sender']['id']
				if sender_id != bot_id and mes.get('message'):
					if 'text' in mes['message']:
						real_text = True
						user_text = mes['message']['text']

		if 'standby' in entry:
			messagings = entry['standby']
			bot_id = entry['id']

			for mes in messagings:
				sender_id = mes['sender']['id']
				if sender_id != bot_id and mes.get('postback'):
					real_text = True
					user_text = mes['postback']['title']

	return bot_id, sender_id, real_text, user_text

def show_fsm():
	love_bot.get_graph().draw('state_diagram.png', prog = 'dot')

if __name__ == '__main__':
	show_fsm()
	app.run()

