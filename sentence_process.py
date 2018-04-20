from snownlp import SnowNLP

import time
import jieba
import jieba.analyse
import selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys 

def get_emotion(text, emotion_upper_bound, emotion_lower_bound, emotion_kind_list):
	text = u"{}".format(text)
	sentence = SnowNLP(text)
	emotion_value = sentence.sentiments

	if emotion_value >= emotion_upper_bound:
		return emotion_kind_list[0]
	elif emotion_value < emotion_lower_bound:
		return emotion_kind_list[2]
	else:
		return emotion_kind_list[1]

def get_keyword(input_word, k):
	result = jieba.analyse.extract_tags(input_word)

	keyword_list = result[:k]
	keyword = ''.join(k for k in keyword_list)

	return keyword

def ckip(text):
	url = 'http://140.116.245.151/NER_news_fe/'

	options = webdriver.ChromeOptions()
	options.add_argument('headless')
	driver = webdriver.Chrome(chrome_options=options, executable_path='chromedriver/chromedriver')#chromedriver path
	driver.get(url)

	input_text = driver.find_element_by_id('inputSentence')
	input_text.clear()
	input_text.send_keys(text)

	driver.find_element_by_css_selector('.btn.btn-default.my-btn').click()
	time.sleep(0.1)
	page_source = driver.page_source
	driver.close() 

	# seperate object (people)
	object_data_str = page_source.split('<div id="show-objlist" class="show-area">')[1]
	object_data_str = object_data_str.split('div')[0]
	object_data_list = object_data_str.split('span')
	object_list = []

	for ob in object_data_list:
		ob = ob.replace('<', '')
		ob = ob.replace('>', '')
		ob = ob.replace('/', '')
		ob = ob.replace(' ', '')
		ob = ob.replace('\n', '')
		ob = ob.replace('\t', '')
		ob = ob.replace('\xa0', '')

		if ob != '':
			object_list.append(ob)

	# seperate simple event
	event_data_str = page_source.split('<div id="show-felist" class="show-area">')[1]
	event_data_str = event_data_str.split('div')[0]
	event_data_str = event_data_str.split('span')
	event_list = []

	for ev in event_data_str:
		ev = ev.split('.')
		if len(ev) > 1:
			ev = ev[1]
			ev = ev.replace('<', '')
			ev = ev.replace('>', '')
			ev = ev.replace('/', '')
			ev = ev.replace(' ', '')
			ev = ev.replace('\n', '')
			ev = ev.replace('\t', '')
			ev = ev.replace('\xa0', '')

			if ev != '':
				event_list.append(ev)

	return object_list, event_list

if __name__ == '__main__':
	object_list, event_list = ckip('看在你第一次發的8成會被埋沒送你一顆愛心可憐你好了')




