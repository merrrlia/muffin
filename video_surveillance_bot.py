
import cv2
import os
import time
import telebot
import requests
import datetime
import threading  # Добавьте этот импорт для использования потока
from skimage.metrics import structural_similarity as ssim
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import tkinter as tk
from PIL import Image, ImageTk

# Токен Telegram бота
bot = telebot.TeleBot("#")
chat_id = '#'
token = '#'

# Путь к JSON с ключами Google Диска
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = r".json"

# ID папки на Google Диске, куда будут загружаться изображения
PARENT_FOLDER_ID = "#"

# Параметры камеры
CAMERA_INDEX = 0  # Индекс камеры (0 для встроенной)
IMAGE_FOLDER = r"photo.jpg"
IMAGE_INTERVAL = 15  # Интервал между снимками (в секундах)

# Переменная для хранения предыдущего кадра
prev_frame = None
# Глобальная переменная для управления наблюдением
watching = False

# Инициализация OpenCV
cv2.namedWindow("Camera")
camera = cv2.VideoCapture(CAMERA_INDEX)


# Функция для сравнения двух изображений
def image_similarity(image1_path, image2_path):
    # Загрузка изображений с использованием OpenCV
    image1 = cv2.imread(image1_path)
    image2 = cv2.imread(image2_path)

    # Преобразование изображений в оттенки серого
    gray_image1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
    gray_image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)

    # Вычисление структурного сходства (Structural Similarity Index - SSIM)
    # Функция ssim возвращает индекс структурного сходства и карту различий (не используется в данном коде).
    similarity_index, _ = ssim(gray_image1, gray_image2, full=True)

    # Вывод значений коэффициента сходства и дополнительной информации (опционально)
    print(similarity_index)
    print(_)

    # Возвращение коэффициента сходства между изображениями
    return similarity_index

# Функция для загрузки файла на Google Диск только если обнаружены различия
# Загрузка фотографий на гугл диск
def authenticate():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return creds
def upload_if_difference(prev_frame_path, current_frame_path):
    similarity_index = image_similarity(prev_frame_path, current_frame_path)
    
    # Если обнаружены различия
    threshold = 0.95  # Порог сходства
    if similarity_index < threshold:
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)

        filename = os.path.basename(current_frame_path)
        file_metadata = {
            'name': filename,
            'parents': [PARENT_FOLDER_ID]
        }

        media = MediaFileUpload(current_frame_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media).execute()

        # Отправка уведомления в Telegram при обнаружении изменений
        message = "Обнаружены изменения! Изображение сохранено."
        print("Обнаружены изменения! Изображение сохранено")
        send_notification(message, photo_path=current_frame_path)



# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Привет! Я камера видеонаблюдения. Чтобы получать уведомления, используйте команду /watch.')

# Обработчик команды /stop
@bot.message_handler(commands=['stop'])
def stop_command(message):
    global watching
    watching = False
    bot.send_message(message.chat.id, 'Остановка наблюдения. Для возобновления используйте команду /watch.')

# Обработчик команды /watch
@bot.message_handler(commands=['watch'])
def watch_command(message):
    global watching, prev_frame
    watching = True
    prev_frame = None  # Reset prev_frame
    bot.send_message(message.chat.id, 'Начинаю наблюдение. Чтобы остановить, используйте команду /stop.')
    # Запуск функции watch в отдельном потоке
    threading.Thread(target=watch).start()


# Функция для отправки уведомления в Telegram
def send_notification(message, photo_path=None):
    chat_id = '#'
    token = '#'

    send_text_url = 'https://api.telegram.org/bot{}/sendMessage'.format(token)
    send_photo_url = 'https://api.telegram.org/bot{}/sendPhoto'.format(token)

    # Отправка текстового сообщения
    text_payload = {'chat_id': chat_id, 'text': message}
    response_text = requests.get(send_text_url, params=text_payload).json()

    # Отправка фотографии, если указан путь к фото
    if photo_path:
        files = {'photo': ('kit.jpg', open(photo_path, 'rb'), 'image/jpeg')}
        photo_payload = {'chat_id': chat_id}
        response_photo = requests.post(send_photo_url, params=photo_payload, files=files)

        # You can print or handle the photo response if needed
        print(response_photo.status_code)

    return response_text

# функция запуска камеры через телеграм
def watch():
    global prev_frame
    while watching:
        # запуск съемки
        _, frame = camera.read()

        # Сохранение изображения в папку
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        image_path = os.path.join(IMAGE_FOLDER, f"{current_time}.jpg")
        cv2.imwrite(image_path, frame)
        cleanup_images(IMAGE_FOLDER)

        # Обработка изображения
        if prev_frame is not None:
            # Загрузка на Google Диск только если обнаружены различия
            upload_if_difference(prev_frame, image_path)

        # Сохранение текущего кадра для использования в следующей итерации
        prev_frame = image_path

        # Ожидание указанного интервала перед следующим снимком
        print("Фото сделано.")
        time.sleep(IMAGE_INTERVAL)



# Оптимизация хранений фотографий в папке 
def cleanup_images(folder, max_age_hours=1):
    # Получаем текущее время в секундах
    current_time = time.time()
    # Вычисляем максимальный возраст файла в секундах
    max_age_seconds = max_age_hours * 3600

    # Итерируемся по файлам в указанной папке
    for filename in os.listdir(folder):
        # Создаем полный путь к файлу
        file_path = os.path.join(folder, filename)
        # Вычисляем возраст файла в секундах
        file_age = current_time - os.path.getctime(file_path)

        # Проверяем, превышает ли возраст файла максимально допустимый возраст
        if file_age > max_age_seconds:
            # Удаляем файл, если он старше указанного максимального возраста
            os.remove(file_path)


# Запуск бота в отдельном потоке
bot_thread = threading.Thread(target=bot.polling, args=(None, True))
bot_thread.start()




# Создание Tkinter-окна
root = tk.Tk()
root.title("Camera Viewer")

# Создание метки для отображения изображения
label = tk.Label(root)
label.pack()

# Запуск видеопотока и обновление изображения
camera = cv2.VideoCapture(CAMERA_INDEX)

# Функция для обновления изображения на форме
def update_image(frame, label):
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(image)
    photo = ImageTk.PhotoImage(image=image)
    label.configure(image=photo)
    label.image = photo
def update_camera():
    _, frame = camera.read()
    update_image(frame, label)
    root.after(IMAGE_INTERVAL * 1000, update_camera)
# Обработка закрытия окна
def on_closing():
    global watching
    watching = False
    bot_thread.join()  # Дождитесь завершения потока бота
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Запуск обновления изображения
update_camera()

# Запуск бесконечного цикла главного окна
try:
    root.mainloop()
except KeyboardInterrupt:
    pass  # Игнорируем KeyboardInterrupt
finally:
    on_closing()  # Вызываем on_closing при завершении работы главного окна
