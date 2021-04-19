#!/usr/bin/env python3
import datetime
import logger, csv

log = logger.get_logger(__name__)

if __name__ == "__main__":
    log.info("======================== Start =========================")         

    cfx_data = []
    with open('cfx-data.csv', newline='') as File:  
        reader = csv.reader(File, delimiter='\t')
        for row in reader:
            cfx_data.append(row)
    cfx_data.sort(key=lambda x: int(x[0]))

    state = {"state":"down",
             "diff":int(cfx_data[0][2]),
             "time_start":datetime.datetime.strptime(cfx_data[0][1],"%Y-%m-%d %H:%M:%S.%f"),   # down up_5m up down_5m 
             "deadline":0}   # down up_2m up down_2m 

    k_up_down = 0.85
    k_down_up = 1.25
    k_price_avarage = 0.15 # Процентm на который допустимо превысить среднюю цену
    k_price_estimated = 0.1 # На сколько допустимо превысить рассчетную цену доходности.

    for i in range(1,len(cfx_data)):
        diff_now = int(cfx_data[i][2])
        if diff_now == 0:
            log.error(f"id={cfx_data[i][0]} difficulty = 0")
            continue #Сложность не может быть равна нулю
        time_now = datetime.datetime.strptime(cfx_data[i][1],"%Y-%m-%d %H:%M:%S.%f") #2021-03-24 19:41:07.198087

        if (state["state"] == "down" or state["state"] == "up") and diff_now > k_down_up * state["diff"]: #Сложность повысиластб
            state["state"] = "up_2m"
            state["time_start"] = time_now
            state["deadline"] = 120 # Действует 120 секунд
            log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = up_2m")

        if state["state"] == "up_2m": 
            if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                state["state"] = "up"
                state["time_start"] = time_now
                state["deadline"] = 0 # Действует 120 секунд
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = up")
                state["diff"] = diff_now

        if (state["state"] == "down" or state["state"] == "up") and diff_now < k_up_down * state["diff"]: #Сложность 
            state["state"] = "down_2m"
            state["time_start"] = time_now
            state["deadline"] = 120 # Действует 120 секунд
            log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = down_2m")

        if state["state"] == "down_2m": 
            if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                state["state"] = "down"
                state["time_start"] = time_now
                state["deadline"] = 0 # Действует 120 секунд
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = down")
                state["diff"] = diff_now




        

            

                
        delta = time_now - datetime.datetime.strptime(cfx_data[i-1][1],"%Y-%m-%d %H:%M:%S.%f")
        if delta.seconds > 1800:
            print(f"{cfx_data[i][0]} delta = {delta.seconds}")



