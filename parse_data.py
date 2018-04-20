from dcard import Dcard
import jieba
import jieba.analyse
import copy
import json
import selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys 
import sentence_process
import time

from operator import itemgetter
from gensim.models import Word2Vec
from snownlp import SnowNLP
import operator

import jieba.posseg as pseg
import codecs
from gensim import corpora
from gensim.summarization import bm25
import os
import re


def get_forums(forum, article_num, comment_top_k):
	dcard = Dcard()
	#to get the most popular article
	metas = dcard.forums(forum).get_metas(num=article_num)
	posts = dcard.posts(metas).get()
	articles = dcard.posts(metas).get(content=True, links=False)


	article_dic = {} # {title: {'content': '', 'comment' : [top1, top2, top3 ....], 'tag': []}}

	for article in articles.result():

		if 'content' in article.keys() and 'tags' in article.keys() and 'comments' in article.keys():
			if article['content'] != '' and len(article['comments']) > 0 and 'error' not in article['comments']:
				print(article['comments'])
				tmp_content = article['content']
				tmp_content = tmp_content.replace('\n','')
				tmp_content = tmp_content.replace(' ', '')
				tmp_content = tmp_content.replace('/', '')
				tmp_content = tmp_content.replace('>', '')
				tmp_content = tmp_content.replace('<', '')
				tmp_content = tmp_content.replace('.', '')


				tmp_tags = ''.join(v for v in article['tags'])

				article_dic[article['title']] = {'content': tmp_content, 'tag': tmp_tags, 'comment': []}

				all_comments = copy.copy(article['comments'])
				all_comments = [v for v in all_comments if 'likeCount' in v.keys()]

				sorted_all_comments = sorted(all_comments, key=itemgetter('likeCount'), reverse = True) 
				sorted_all_comments = sorted_all_comments[:comment_top_k]

				for c in sorted_all_comments:
					article_dic[article['title']]['comment'].append(c['content'])

	return article_dic


def get_keyword(input_word, k):
	result = jieba.analyse.extract_tags(input_word)
	keyword_list = result[:k]

	keyword_order = {} # {keyword: index}
	for r in keyword_list:
		keyword_order[r] = input_word.index(r)

	sorted_keyword_order = sorted(keyword_order.items(), key=operator.itemgetter(1))

	keyword = ''.join(k[0] for k in sorted_keyword_order)

	return keyword


def write_article(article_dic):
	with open('dcard_data/dcard_data.json', 'w') as fp:
		json.dump(article_dic, fp)

def embedding_artice_data(dimensions, window, iteration, emb_file1, emb_file2, model1_file, model2_file):

	article_dic = {}
	articleTag_map_title = {}
	title_map_contentkeyword = {}
	k = 20


	with open('dcard_data/dcard_data.json', 'r') as fp:
		article_dic = json.load(fp)

	# save article embedding vector
	first_word_list = []
	second_word_list = []

	for title in article_dic.keys():
		first_embedding = title + article_dic[title]['tag']
		articleTag_map_title[first_embedding] = title

		second_embedding = article_dic[title]['content']
		# get content keyword
		second_embedding_keyword = get_keyword(second_embedding, k)
		title_map_contentkeyword[title] = second_embedding_keyword

		first_word_list.append(first_embedding)
		second_word_list.append(second_embedding_keyword)

	model1 = Word2Vec([first_word_list], size = dimensions, window = window, min_count=0, iter = iteration)
	model2 = Word2Vec([second_word_list], size = dimensions, window = window, min_count=0, iter = iteration)

	model1.wv.save_word2vec_format(emb_file1)
	model2.wv.save_word2vec_format(emb_file2)

	model1.save(model1_file)
	model2.save(model2_file)

	with open('dcard_data/articleTag_map_title.json', 'w') as fp:
		json.dump(articleTag_map_title, fp)
	with open('dcard_data/title_map_contentkeyword.json', 'w') as fp:
		json.dump(title_map_contentkeyword, fp)

def process_comment_data():
	with open('dcard_data/dcard_data.json', 'r') as fp:
		article_dic = json.load(fp)

	article_map_commentEvent_dic = {} #{title: [{'event': , 'sentiment_value': }, {'event': , 'sentiment_value': }, ....]}
	k = 5
	count = 0

	for title in article_dic.keys():
		article_map_commentEvent_dic[title] = []

		comment_list = copy.copy(article_dic[title]['comment'])
		
		for comment in comment_list:

			comment = process_comment(comment)
			
			if comment != '':
				keyword = get_keyword(comment, k)

				text = u"{}".format(comment)
				sentence = SnowNLP(text)
				emotion_value = sentence.sentiments
				

				article_map_commentEvent_dic[title].append({'keyword': keyword, 'sentiment_value': emotion_value, 'comment': comment})

	with open('dcard_data/article_map_commentEvent.json', 'w') as fp:
		json.dump(article_map_commentEvent_dic, fp)


def process_comment(comment):

	clear_word = ['我們','我','樓上','樓下']
	replace_word = {'樓主':'你'}

	for clear in clear_word:
		comment = comment.replace(clear, '')

	for r in replace_word.keys():
		comment = comment.replace(r, replace_word[r])

	c_list = comment.split('\n')
	new_comment_list = []
	for c in c_list:
		if 'B' not in c:
			new_comment_list.append(c)

	new_comment = '\n'.join(v for v in new_comment_list)

	return new_comment

def preprocess_bm25():
	with open('dcard_data/dcard_data.json', 'r') as fp:
		article_dic = json.load(fp)	

	corpus = []
	title_list = []
	total_data = {}
	for title in article_dic.keys():
		content_split = jieba.cut(article_dic[title]['content'], cut_all=False)
		content_split = list(content_split)
		corpus.append(content_split)
		title_list.append(title)

	total_data['corpus'] = corpus
	total_data['title_list'] = title_list

	with open('dcard_data/bm25_corpus.json', 'w') as fp:
		json.dump(total_data, fp)	


if __name__ == '__main__':

	article_num = 2000
	comment_top_k = 10
	dcard_forum = 'relationship'

	dimensions = 200
	window = 10
	iteration = 20

	emb_file1 = 'dcard_data/dcard_title_tags_embedding.txt'
	emb_file2 = 'dcard_data/dcard_content_embedding.txt'
	model1_file = 'dcard_data/dcard_title_tags_model'
	model2_file = 'dcard_data/dcard_content_model'

	### preprocessing
	#article_dic = get_forums(dcard_forum, article_num,comment_top_k)
	#write_article(article_dic)
	#embedding_artice_data(dimensions, window, iteration, emb_file1, emb_file2, model1_file, model2_file)
	#process_comment_data()

	#preprocess_bm25()

