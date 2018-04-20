import sentence_process
import requests
import json
import time
import random
import jieba
import operator
import os
import re
import codecs
import copy
import jieba.posseg as pseg

from operator import itemgetter
from gensim.models import Word2Vec
from snownlp import SnowNLP
from gensim import corpora
from gensim.summarization import bm25
from googlesearch import search


model1_file = 'dcard_data/dcard_title_tags_model'
model2_file = 'dcard_data/dcard_content_model'
title_map_contentkeyword_file = 'dcard_data/title_map_contentkeyword.json'
dcard_data_file = 'dcard_data/dcard_data.json'
article_map_commentEvent_file = 'dcard_data/article_map_commentEvent.json'
bm25_corpus_file = 'dcard_data/bm25_corpus.json'

sim1_weight = 0.5
sim2_weight = 0.5


def map_conversation_article(user_people, user_event, user_reason, user_total_context):

    text = u"{}".format(user_total_context)
    sentence = SnowNLP(text)
    user_kimochi = sentence.sentiments

    with open(title_map_contentkeyword_file, 'r') as fp:
        title_map_contentkeyword = json.load(fp)
    with open(dcard_data_file, 'r') as fp:
        article_dic = json.load(fp)

    dcard_similarity_dic = {} #{title: similarity_value}

    ## bm25
    title_bm25_dic = implement_bm25(user_total_context)

    ## compare title_tags and user_people,event,reason
    ### process model1
    model1 = Word2Vec.load(model1_file)

    compare_word1 = user_people + user_event + user_reason
    model1.build_vocab([[compare_word1]], update = True)
    ### process model2
    model2 = Word2Vec.load(model2_file)

    compare_word2 = user_total_context
    model2.build_vocab([[compare_word2]], update = True)

    for title in article_dic.keys():
        compare_articleTag = title + article_dic[title]['tag']
        compare_contentKeyword = title_map_contentkeyword[title]

        sim1 = model1.wv.similarity(compare_articleTag, compare_word1)
        #sim2 = model2.wv.similarity(compare_contentKeyword, compare_word2)
        sim2 = title_bm25_dic[title]

        dcard_similarity_dic[title] = sim1 * sim1_weight + sim2 * sim2_weight   

    sorted_dcard_similarity_list = sorted(dcard_similarity_dic.items(), key=operator.itemgetter(1), reverse = True)
    most_similar_title = sorted_dcard_similarity_list[0][0]

    answer = map_article_answer(most_similar_title, user_kimochi)
    return answer

def implement_bm25(user_total_context):
    with open(bm25_corpus_file, 'r') as fp:
        bm25_corpus = json.load(fp)

    corpus = bm25_corpus['corpus']
    title_list = bm25_corpus['title_list']
    # create bm25
    bm25Model = bm25.BM25(corpus)
    average_idf = sum(map(lambda k: float(bm25Model.idf[k]), bm25Model.idf.keys())) / len(bm25Model.idf.keys())

    user_total_context_list = jieba.cut(user_total_context, cut_all=False)
    user_total_context_list = list(user_total_context_list)

    scores = bm25Model.get_scores(user_total_context_list,average_idf)

    title_bm25_dic = {}

    for x in range(0, len(title_list)):
        title_bm25_dic[title_list[x]] = scores[x]

    return title_bm25_dic


def map_article_answer(most_similar_title, user_kimochi):
    with open(dcard_data_file, 'r') as fp:
        article_dic = json.load(fp)
    with open(article_map_commentEvent_file, 'r') as fp:
        article_map_commentEvent = json.load(fp)

    candidate_comment = article_map_commentEvent[most_similar_title]

    close_sentiment_value = {}

    for comment in candidate_comment:
        value = abs(user_kimochi - float(comment['sentiment_value']))
        close_sentiment_value[comment['comment']] = value

    sorted_close_sentiment_value = sorted(close_sentiment_value.items(), key=operator.itemgetter(1))
    
    reply_comment_list = []

    for s in sorted_close_sentiment_value:
        if s[0] != '' and len(s[0]) > 5:
            reply_comment = s[0]
            reply_comment = reply_comment.replace('\n', ' ')
            reply_comment_list.append(reply_comment)

        if len(reply_comment_list) == 2:
            break

    default = ['船到橋頭自然直', '我相信會有辦法解決的']
    if len(reply_comment_list) == 1:
        reply_comment_list.append(default[1])
    if len(reply_comment_list) == 0:
        reply_comment_list = copy.copy(default)

    print(reply_comment_list)
    return reply_comment_list

def get_username(user_id, PAGE_ACCESS_TOKEN):
    profile_api = 'https://graph.facebook.com/v2.6/{user_id}?access_token={page_access_token}'.format(user_id = user_id, page_access_token = PAGE_ACCESS_TOKEN)
    resp = requests.get(profile_api)
    content = json.loads(resp.text)

    user_name = content['first_name']
    user_gender = content['gender']

    return user_name, user_gender

def create_button(receiver, PAGE_ACCESS_TOKEN, button_payload):

    button_data = {
        "attachment":{
            "type": "template",
            "payload": button_payload
        }
    }
    send_message(receiver, button_data, PAGE_ACCESS_TOKEN, 'button')


def send_message(receiver, message, PAGE_ACCESS_TOKEN, type_str):
    post_message_url = 'https://graph.facebook.com/v2.6/me/messages?access_token={token}'.format(token=PAGE_ACCESS_TOKEN)

    if type_str == 'text':
        response_message = json.dumps({'recipient': {'id': receiver}, 'message': {'text': message}})
    if type_str == 'button':
        response_message = json.dumps({'recipient': {'id': receiver}, 'message': message})
    
    req = requests.post(post_message_url, 
                            headers={'Content-Type': 'application/json'}, 
                            data=response_message)
    
    if req.status_code != 200:
        print(req.text)


def process_get_data(user_text, people_str, event_str):

    people_list, event_list = sentence_process.ckip(user_text)
    people_list = list(set(people_list))
    event_list = list(set(event_list))

    people_str += ''.join(v for v in people_list)
    event_str += ''.join(v for v in event_list)

    return people_str, event_str

## setting bot transition
class Bot(object):
    def __init__(self, emotion_upper_bound, emotion_lower_bound, emotion_kind_list, PAGE_ACCESS_TOKEN):
        self.emotion_upper_bound = emotion_upper_bound
        self.emotion_lower_bound = emotion_lower_bound
        self.emotion_kind_list = emotion_kind_list
        self.PAGE_ACCESS_TOKEN = PAGE_ACCESS_TOKEN

        self.bot_setting()
        self.load_corpus()

    def bot_setting(self):
        self.bot_id = ''
        self.sender_id = ''
        self.people = ''
        self.event = ''
        self.reason = ''
        self.reply = ''
        self.total_context = ''
        self.user_name = ''
        self.user_gender = ''

        self.start = 0
        self.stuck_people_count = 0
        self.stuck_event_count = 0
        self.stuck_reason_count = 0
        self.stuck_greeting_count = 0
        self.stuck_reply_count = 0

    def load_corpus(self):
        conversation_file = 'corpus/conversation_corpus.json'

        with open(conversation_file) as fp:
            conversation_json = json.load(fp)

        self.conversation_corpus = conversation_json

    def get_time(self):
        time_data = time.localtime()
        time_break_hour = [5, 13, 18]
        hour = int(time_data.tm_hour)

        if hour <= time_break_hour[0] or hour > time_break_hour[2]:
            self.daytime = 'evening'
        if hour > time_break_hour[0] and hour <= time_break_hour[1]:
            self.daytime = 'morning'
        if hour > time_break_hour[1] and hour <= time_break_hour[2]:
            self.daytime = 'afternoon'


    def first_meet(self, message_info = ''):
        print('fist meet')

    def if_start(self, message_info = ''):
        return self.start

    def if_get_nothing(self, message_info = ''):
        if self.people == '' and self.event == '' and self.reason == '':
            return True
        return False

    def if_get_event_no_people(self, message_info):
        if self.event != '' and self.people == '':
            return True
        return False

    def if_get_people_no_event(self, message_info):
        if self.people != '' and self.event == '':
            return True
        return False        

    def if_get_people(self, message_info = ''):
        if self.people != '':
            return True
        return False

    def if_get_event(self, message_info = ''):
        if self.event != '':
            print('has event')
            return True
        return False

    def if_get_reason(self, message_info = ''):
        if self.reason != '':
            return True
        return False

    def if_stuck_people(self, message_info = ''):
        #print('stuck_people num: ', self.stuck_people_count)
        if self.stuck_people_count > 0:
            return True
        return False  

    def if_collect_complete(self, message_info = ''):
        if self.people != '' and self.event != '' and self.reason != '' :
            return True
        return False

    def process_message(self, message_info):
        self.get_time()
        self.start = 1
        
        self.bot_id = message_info['bot_id']
        self.sender_id = message_info['sender_id']
        user_text = message_info['user_text']

        self.total_context += user_text

        user_emotion_kind = sentence_process.get_emotion(user_text, self.emotion_upper_bound, self.emotion_lower_bound, self.emotion_kind_list)

        self.user_name, self.user_gender = get_username(self.sender_id, self.PAGE_ACCESS_TOKEN)
        hello_word = self.conversation_corpus['greeting']['time'][self.daytime][user_emotion_kind]

        # collect people and event data
        self.people, self.event = process_get_data(user_text, self.people, self.event)


        if self.people == '' and self.event == '':
            send_word = self.user_name + hello_word 
            send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')
            
            send_word = random.choice(self.conversation_corpus['introduction'])
            send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')

        if self.people == '' and self.event != '':
            if self.stuck_greeting_count < len(self.conversation_corpus['ask_people']) + 1:

                send_word = random.choice(self.conversation_corpus['ask_people'][self.stuck_people_count - 1])
                #print('people: ' + self.people + ' "event": ' + self.event + 'reason: ' + self.reason)

                send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')

                self.stuck_greeting_count += 1
            else:
                self.people = user_text
                self.stuck_greeting_count = 0

        elif self.people != '' and self.event == '':
            self.stuck_people_count += 1
        elif self.people != '' and self.event != '':
            self.stuck_people_count = 0
            self.stuck_greeting_count = 0

    def got_people(self, message_info):

        self.bot_id = message_info['bot_id']
        self.sender_id = message_info['sender_id']
        user_text = message_info['user_text']

        self.total_context += user_text

        if self.stuck_people_count > 1:
            self.people, self.event = process_get_data(user_text, self.people, self.event)

        if self.event == '':
            if self.stuck_people_count < len(self.conversation_corpus['ask_event']) + 1:

                send_word = random.choice(self.conversation_corpus['ask_event'][self.stuck_people_count - 1])
                #print('people: ' + self.people + ' "event": ' + self.event + 'reason: ' + self.reason)

                send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')

                self.stuck_people_count += 1
            else:
                self.event = user_text
                self.stuck_people_count = 0

        else:
            self.stuck_people_count = 0


    def got_event(self, message_info):

        self.bot_id = message_info['bot_id']
        self.sender_id = message_info['sender_id']

        if self.stuck_event_count == 0:

            send_word = random.choice(self.conversation_corpus['ask_reason'])

            #print('people: ' + self.people + ' "event": ' + self.event + 'reason: ' + self.reason)
        
            self.stuck_event_count += 1

            send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text') 
        else:
            self.reason = message_info['user_text']

            self.total_context += message_info['user_text']

            self.stuck_event_count = 0


    def got_reason(self, message_info):

        self.bot_id = message_info['bot_id']
        self.sender_id = message_info['sender_id']

        
        reason_sentiment_tag = sentence_process.get_emotion(self.reason, self.emotion_upper_bound, self.emotion_lower_bound, self.emotion_kind_list)
        send_word = random.choice(self.conversation_corpus['pause'][reason_sentiment_tag]) + '\n'
        
        #print('people: ' + self.people + ' "event": ' + self.event + 'reason: ' + self.reason)

        send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')

        reply_answer = map_conversation_article(self.people, self.event, self.reason, self.total_context)

        self.reply = reply_answer
        send_message(self.sender_id, self.reply[0], self.PAGE_ACCESS_TOKEN, 'text') 
    
    def end_reply(self, message_info):
        self.stuck_reply_count += 1
        self.bot_id = message_info['bot_id']
        self.sender_id = message_info['sender_id']
        user_text = message_info['user_text']

        ask_title1 = '認同'
        ask_title2 = '不認同'

        ask_payload = {
            "template_type": "button",
            "text": self.user_name + '你覺得呢？認同這個想法嗎？',
            'buttons': [
                 {
                     'type': 'postback',
                     'title': ask_title1,
                     'payload': 1
                 },
                 {
                     'type': 'postback',
                     'title': ask_title2,
                     'payload': -1
                 }
            ]
        }

        if user_text != ask_title1 and user_text != ask_title2:
            create_button(self.sender_id, self.PAGE_ACCESS_TOKEN, ask_payload)

        elif user_text == ask_title2:
            reply = '我再想想...😔'
            send_message(self.sender_id, reply, self.PAGE_ACCESS_TOKEN, 'text')

            reply = self.reply[1]
            send_message(self.sender_id, reply, self.PAGE_ACCESS_TOKEN, 'text')
         
        if user_text == ask_title2 or user_text == ask_title1:

            gender = '女孩' if self.user_gender == 'female' else '男孩'
            search_link = ''
            search_word = self.people + ' ' + self.event + ' ' + self.reason

            for url in search(search_word, tld='es', lang='es', stop=1):
                search_link = url
                break

            send_word = '當'+gender+'遇到這樣的問題，或許你可以參考看看這個連結喔！\n'+search_link
            send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')

            send_word = random.choice(self.conversation_corpus['end_reply'])
            send_message(self.sender_id, send_word, self.PAGE_ACCESS_TOKEN, 'text')

            #reset
            self.bot_setting()
            self.load_corpus()

