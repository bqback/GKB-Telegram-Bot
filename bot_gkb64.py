#!/usr/bin/python
# -*- coding: utf-8 -

# Документация (англ): http://python-telegram-bot.readthedocs.io/en/stable/telegram.html
# Примеры: https://github.com/python-telegram-bot/python-telegram-bot/tree/master/examples

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler, ConversationHandler)
import logging
import smtplib
import re
import os
import sys
import wget
from threading import Thread
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
					level=logging.INFO)
logger = logging.getLogger(__name__)

# Вставлять новую ссылку при добавлении/удалении новых вопросов
faq_url = 'http://telegra.ph/CHasto-zadavaemye-voprosy-03-19'

# Всё хранится в соответствующих переменных среды, чтобы я мог заливать это на GitHub без зазрения совести :^)
api_key = os.environ['BOT_API_KEY']
email_login = os.environ['MAIL_LOGIN']
email_pwd = os.environ['MAIL_PASSWORD']

# Ссылка на скрипт на GitHub для проверки на апдейты
github_link = 'https://raw.githubusercontent.com/bqback/GKB-Telegram-Bot/master/bot_gkb64.py'

# Блок клавиатур для простого прикрепления к сообщениям бота
# Формат [[ряд1_кнопка1, ряд1_кнопка2, ...], [ряд2_кнопка1, ряд2_кнопка2, ...], ...]
# Стоит учеть ограниченную ширину экранов смартфонов при добавлении нескольких кнопок в ряд
start_menu_keyboard = [["ЧаВо"], ["Задать вопрос"], ["Пожелания и предложения"], ["Жалобы и претензии"], ["Контактные данные"]]
start_markup = ReplyKeyboardMarkup(start_menu_keyboard, resize_keyboard=True)

return_menu_keyboard = [["Вернуться в главное меню"]]
return_markup = ReplyKeyboardMarkup(return_menu_keyboard, resize_keyboard=True)

cancel_menu_keyboard = [["Отмена"]]
cancel_markup = ReplyKeyboardMarkup(cancel_menu_keyboard, resize_keyboard=True)

faq_menu_keyboard = [["Продолжить"], ["Вернуться в главное меню"]]
faq_markup = ReplyKeyboardMarkup(faq_menu_keyboard, resize_keyboard=True)

info_exists_menu_keyboard = [["Использовать"], ["Ввести заново"], ["Вернуться в главное меню"]]
info_markup = ReplyKeyboardMarkup(info_exists_menu_keyboard, resize_keyboard=True)

info_input_error_keyboard = [["Попробовать снова"], ["Оставить"]]
info_error_markup = ReplyKeyboardMarkup(info_input_error_keyboard, resize_keyboard=True)

info_missing_keyboard = [["Вернуться и ввести имя"], ["Вернуться и ввести контактные данные"], ["Продолжить ввод сообщения"]]
info_missing_markup = ReplyKeyboardMarkup(info_missing_keyboard, resize_keyboard=True)

contact_info_keyboard = [["Номер телефона"], ["Почтовый ящик"], ["Продолжить"]]
contact_markup = ReplyKeyboardMarkup(contact_info_keyboard, resize_keyboard=True)

continue_keyboard = [["Продолжить"]]
continue_markup = ReplyKeyboardMarkup(continue_keyboard, resize_keyboard=True)


# Регулярные выражения для отбора телефонных номеров и почтовых ящиков
email_regex = re.compile("([a-zA-Z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+\/=?^_`{|}~-]+)*"
							"(@|\sat\s)"
							"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
							"(\.|\sdot\s))+"
							"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)")
phone_regex = re.compile("(\(|)\d{3}(\)|)(\s|\-|)\d{3}(\s|\-|)\d{2}(\s|\-|)\d{2}")

CHOICE, SUBJECT, NAME, CONTACT_INFO, PHONE_NUM, EMAIL, MSG_TEXT, FAQ = range(8)

# Дефолтное меню
def start(bot, update):
	update.message.reply_text("Здравствуйте, я – автоматический помощник "
								"клинической больницы им В. В. Виноградова.",
		reply_markup=start_markup)
	return CHOICE

# ЧаВо
def faq_button(bot, update):
	update.message.reply_text(faq_url,
		reply_markup=return_markup)
	return CHOICE

# Задать вопрос
def ask_question(bot, update, user_data, chat_data):
	update.message.reply_text("Здесь Вы можете задать любой интересующий вас вопрос.")
	update.message.reply_text("Для начала проверьте, нет ли Вашего вопроса в списке наших часто задаваемых вопросов.\n"+faq_url, 
			reply_markup=faq_markup)
	chat_data['subj'] = u"Вопрос"
	return FAQ

# Пожелание или предложение
def suggestion_button(bot, update, user_data, chat_data):
	update.message.reply_text("Здесь вы можете отправить своё пожелание или предложение")
	chat_data['subj'] = u"Предложение"
	get_name(bot, update, user_data, chat_data)
	return NAME

# Жалоба или претензия
def complaint_button(bot, update, user_data, chat_data):
	update.message.reply_text("Здесь вы можете отправить свою жалобу или претензию")
	chat_data['subj'] = u"Жалоба"
	get_name(bot, update, user_data, chat_data)
	return NAME

# Контактные данные
def contact_info(bot, update):
	update.message.reply_text("Телефон: +7 (495) 103-46-66 "
								"\n\n"
								"Адрес: г. Москва, ул. Вавилова, 61"
								"\n\n"
								"Сайт: http://gkb64.ru"
								"\n\n"
								"E-mail: info@gkb64.ru",
		reply_markup=return_markup)
	return CHOICE	

# Отправка сообщений
def msg_handle(bot, update, user_data, chat_data):
	msgtext = update.message.text
	author_name = user_data['name']
	email_addr = user_data['email']
	phone_numb = user_data['phone']
	fromaddr = email_login
	toaddr = email_login
	msg = MIMEMultipart()
	msg['From'] = fromaddr
	msg['To'] = toaddr
	msg['Subject'] = chat_data['subj']

	body = u'Имя: ' + author_name + u'\n\nДанные для обратной связи:' + u'\nАдрес электронной почты: ' + email_addr + u'\nТелефон: ' + phone_numb +	u'\n\nТекст жалобы:\n' + msgtext
	msg.attach(MIMEText(body, "plain", "UTF-8"))

	server = smtplib.SMTP('smtp.gmail.com', 587)
	server.starttls()
	server.login(fromaddr, email_pwd)
	text = msg.as_string()
	server.sendmail(fromaddr, toaddr, text)

	update.message.reply_text(u"Сообщение отправлено!",
		reply_markup=return_markup)
	return CHOICE

# Более-менее универсальная функция сохранения данных
def save_info(bot, update, user_data, chat_data):
	text = update.message.text
	category = chat_data['acq_data']
	if category == 'phone' and not phone_regex.match(text):
		update.message.reply_text(u'Этот номер не похож на мобильный номер', reply_markup=info_error_markup)
	elif category == 'email' and not email_regex.match(text):
		update.message.reply_text(u'Этот адрес не похож на правильный почтовый адрес', reply_markup=info_error_markup)
	else:
		user_data[category] = text
		update.message.reply_text(u'Данные сохранены!', 
			reply_markup=continue_markup)
		chat_data['acq_data'] = ''
	if category == 'name':
		return NAME
	elif category == 'phone':
		return PHONE_NUM
	elif category == 'email':
		return EMAIL

# Получаем имя для обращения
def get_name(bot, update, user_data, chat_data):
	text = update.message.text
	if not user_data.get('name', False):
		user_data['name'] = ''
	if text == u'Ввести заново':
		user_data['name'] = ''
	if user_data['name'] == '':
		chat_data['acq_data'] = 'name'
		update.message.reply_text("Как к Вам обращаться?"
									"\n\n(Можете ввести /skip для пропуска или нажать Вернуться для возвращения в главное меню)", 
			reply_markup=return_markup)
	else:
		update.message.reply_text(u"Использовать сохранённое имя? ({})".format(user_data['name']), 
			reply_markup=info_markup)
	return NAME

# Получаем контактные данные (добавить отображение имеющихся данных)
def get_contacts(bot, update, user_data, chat_data):
#	existing_data = dict()
#	data_string = list()
	if not user_data.get('phone', False):
		user_data['phone'] = ''
	if not user_data.get('email', False):
		user_data['email'] = ''
#	if user_data['phone']:
#		existing_data[u'Номер телефона'] = user_data['phone']
#	if user_data['email']:
#		existing_data[u'Почтовый адрес'] = user_data['email']
#	if not existing_data:
#		update.message.reply_text(u"У Вас отсутствуют контактные данные!")
#	else:
#		for key in existing_data:
#			data_string.append(u'{}: {}'.format(key, existing_data[key]))
#		result = "\n".join(data_string)
#		update.message.reply_text(u"У Вас указаны следующие контактные данные: {}", format(result))
	update.message.reply_text("Оставьте ваши контактные данные"
								" или нажмите Продолжить для перехода к отправке текста",
		reply_markup=contact_markup)
	return CONTACT_INFO

# Получаем номер телефона
def get_phone(bot, update, user_data, chat_data):
	text = update.message.text
	if text == u'Ввести заново':
		user_data['phone'] = ''
	if user_data['phone'] == '':
		chat_data['acq_data'] = 'phone'
		update.message.reply_text("Введите свой номер телефона без +7 (десять цифр)"
									"\n\n(Или нажмите Отмена для ввода других контактных данных)", 
			reply_markup=cancel_markup)
	else:
		update.message.reply_text(u"Использовать сохранённый номер? ({})".format(user_data['phone']), 
			reply_markup=info_markup)
	return PHONE_NUM

# Получаем почтовый адрес
def get_email(bot, update, user_data, chat_data):
	text = update.message.text
	if text == u'Ввести заново':
		user_data['email'] = ''
	if user_data['email'] == '':
		chat_data['acq_data'] = u'email'
		update.message.reply_text("Введите свой почтовый адрес"
									"\n\n(Или нажмите Отмена для ввода других контактных данных)", 
			reply_markup=cancel_markup)
	else:
		update.message.reply_text(u"Использовать сохранённый адрес? ({})".format(user_data['email']), 
			reply_markup=info_markup)
	return EMAIL

# Получаем текст сообщения, убеждаемся, что пользователь не хочет оставить контактные данные или имя
def get_msg_text(bot, update, user_data, chat_data):
	text = update.message.text
	inclusion = ''
	missing_data = list()
	if (user_data['name'] == '' or (user_data['phone'] == '' and user_data['email'] == '')) and not text == u'Продолжить ввод сообщения':
		if user_data['name'] == '':
			missing_data.append(u'имя')
		if (user_data['phone'] == '' and user_data['email'] == ''):
			missing_data.append(u'контактные данные')
		update.message.reply_text(u'Вы уверены, что не хотите оставить {} для обратной связи?'.format(", ".join(missing_data)),
			reply_markup=info_missing_markup)
	else: 
		if chat_data['subj'] == u'Вопрос':
			inclusion = u'свой вопрос'
		elif chat_data['subj'] == u'Предложение':
			inclusion = u'своё пожелание или предложение'
		elif chat_data['subj'] == u'Жалоба':
			inclusion = u'свою жалобу или претензию'
		update.message.reply_text(u'Опишите {}, '
								u'нажмите Отмена для возврата к вводу контактных данных '
								u'или Вернуться для возврата в главное меню'.format(inclusion),
		reply_markup=return_markup)
	return MSG_TEXT

def help(bot, update):
    update.message.reply_text(u"Напиши /start")

# Проверяем соответствие данных регулярным выражениям в начале программы, потому что иначе нельзя будет связаться
def warning_error(bot, update, chat_data):
	category = chat_data['acq_data']
	update.message.reply_text("ВНИМАНИЕ: Если данные введены неправильно, мы не сможем с вами связаться!", 
		reply_markup=info_error_markup)
	if category == 'phone':
		return PHONE_NUM
	elif category == 'email':
		return EMAIL

def error(bot, update, error):
    # пишет ошибки, вызванные командами и обновлениями
    logger.warning('Update "%s" caused error "%s"', update, error)

def main():
	# токен
	updater = Updater(token=api_key)

	# управляет там всяким
	dp = updater.dispatcher


	conv_handler = ConversationHandler(
		entry_points=[CommandHandler('start', start)],

		states={
			CHOICE: [
				RegexHandler('^/start$',
								start),
				RegexHandler(u'^(ЧаВо)$',
								faq_button),
				RegexHandler(u'^(Задать вопрос)$',
					 			ask_question,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(Пожелания и предложения)$',
					 			suggestion_button,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(Жалобы и претензии)$',
					 			complaint_button,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(Контактные данные)$', 
					 			contact_info)
			],
			FAQ: [
				RegexHandler(u'^(Продолжить)', 
								get_name,
								pass_user_data=True,
								pass_chat_data=True)
			],
			PHONE_NUM: [
				RegexHandler(u'^Вернуться в главное меню$', start),
				RegexHandler(u'^(Отмена|Использовать|Продолжить)$',
								get_contacts,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(/skip)$',
								get_msg_text,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(Ввести заново|Попробовать снова)$',
					 			get_phone,
					 			pass_user_data=True,
					 			pass_chat_data=True),
				RegexHandler(u'^(Оставить)$',
								warning_error,
								pass_chat_data=True),
				MessageHandler(Filters.text,
					 			save_info,
					 			pass_user_data=True,
					 			pass_chat_data=True)
			],
			EMAIL: [
				RegexHandler(u'^Вернуться в главное меню$', start),
				RegexHandler(u'^(Отмена|Использовать|Продолжить)$',
								get_contacts,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(/skip)$',
								get_msg_text,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(Ввести заново|Попробовать снова)$',
					 			get_email,
					 			pass_user_data=True,
					 			pass_chat_data=True),
				RegexHandler(u'^(Оставить)$',
								warning_error,
								pass_chat_data=True),
				MessageHandler(Filters.text,
					 			save_info,
					 			pass_user_data=True,
					 			pass_chat_data=True)
			],
			CONTACT_INFO: [
				RegexHandler(u'^Вернуться в главное меню$', start),
				RegexHandler(u'^(Номер телефона)$',
								get_phone,
								pass_user_data=True,
					 			pass_chat_data=True),
				RegexHandler(u'^(Почтовый ящик)$',
						   		get_email,
								pass_user_data=True,
					 			pass_chat_data=True),
				RegexHandler(u'^(Продолжить)$',
						   		get_msg_text,
								pass_user_data=True,
					 			pass_chat_data=True)
			],
			NAME: [
				RegexHandler(u'^Вернуться в главное меню$', start),
				RegexHandler(u'^(Использовать|/skip|Продолжить)$',
								get_contacts,
								pass_user_data=True,
								pass_chat_data=True),
				RegexHandler(u'^(Ввести заново)$',
					 			get_name,
					 			pass_user_data=True,
					 			pass_chat_data=True),
				MessageHandler(Filters.text,
					 			save_info,
					 			pass_user_data=True,
					 			pass_chat_data=True)
			],
			MSG_TEXT: [
				RegexHandler(u'^(Вернуться и ввести имя)$',
					   			get_name,
					 			pass_user_data=True,
					   			pass_chat_data=True),
				RegexHandler(u'^(Вернуться и ввести контактные данные)$',
					   			get_contacts,
					 			pass_user_data=True,
					   			pass_chat_data=True),
				RegexHandler(u'^(Продолжить ввод сообщения)$',
								get_msg_text,
					 			pass_user_data=True,
					   			pass_chat_data=True),
				MessageHandler(Filters.text,
					 			msg_handle,
					 			pass_user_data=True,
					 			pass_chat_data=True)				
			]
			
		},

		fallbacks=[RegexHandler(u'^Вернуться в главное меню$', start)]
	)
	
	help_handler = CommandHandler('help', help)

	dp.add_handler(conv_handler)
	dp.add_handler(help_handler)

	def stop_and_restart():
		updater.stop()
		os.execl(sys.executable, sys.executable, *sys.argv)

	def check_for_updates():
		wget.download(github_link, 'bot_compare.py')
		if filecmp.cmp('bot_gkb64.py', 'bot_compare.py'):
			os.remove('bot_compare.py')
			update.message.reply_text("Test!")
		sleep(86400)

	def restart(bot, update):
		update.message.reply_text("Перезапуск...")
		Thread(target=stop_and_restart).start()

	dp.add_handler(CommandHandler('r', restart, filters=Filters.user(username=["@jazzforyoursoul", "@OlgaAshug"])))
	dp.add_handler(CommandHandler('update', check_for_updates, filters=Filters.user(username=["@jazzforyoursoul", "@OlgaAshug"])))

	dp.add_error_handler(error)

	updater.start_polling()

	updater.idle()

if __name__ == '__main__':
	main()	