import json
import time
import logging
from multiprocessing import Process
from queue import Empty
from redis import Redis
from clickhouse_driver import Client
import requests
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')

# Initialize ClickHouse client
clickhouse_client = Client(host='localhost', port=9000, database='default')

# Redis configuration
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
redis_queue_name = 'search_tasks'

# External service URL
external_service_url = 'https://pastebin.com/'

def search_and_send_task(task):
    try:
        logging.info(f"Processing task: {task}")
        # Extract fields from the task
        task_id, ipv4, mac = task['id'], task['ipv4'], task['mac']

        # Search for username in ClickHouse
        result = clickhouse_client.execute("SELECT username FROM accounts WHERE ipv4 = '{}' AND mac = '{}' LIMIT 1".format(ipv4, mac))

        if result:
            # Username found, send to external service
            payload = {'username': result[0]}
            response = requests.post(external_service_url, json=payload)

            if response.status_code == 200:
                # Print and log successful search result
                logging.info("Successful search result. External service response: %s", response.text)
                with open('successful_search_results.txt', 'a') as file:
                    file.write("{} - {}\n".format(time.strftime('%Y-%m-%d %H:%M:%S'), response.url))
            else:
                # Print and log non-200 status code from the external service
                logging.warning("External service returned non-200 status code: %s", response.status_code)
                # Print and log non-200 status code from the external service
                print("External service returned non-200 status code:", response.status_code)
    except Exception as e:
        # Print and log any processing errors with traceback
        logging.exception("Error processing task")
        # Print and log any processing errors
        print("Error processing task: {}".format(e))
def process_queue():
    redis = Redis(host=redis_host, port=redis_port)

    while True:
        try:
            # Retrieve task from the Redis queue
            task_json = redis.blpop(redis_queue_name, timeout=10)[1]
            task = json.loads(task_json)
            search_and_send_task(task)
        except Empty:
            # Redis queue is empty, continue waiting
            pass
        except Exception as e:
            logging.exception("Error processing task")

if __name__ == '__main__':
    # Start multiple processes for parallel queue processing
    num_processes = 4
    processes = [Process(target=process_queue) for _ in range(num_processes)]

    for process in processes:
        process.start()

    for process in processes:
        process.join()
