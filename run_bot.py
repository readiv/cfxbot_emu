#!/usr/bin/env python3
import datetime
import logger, csv, config
from nicehash_emu import Nice

log = logger.get_logger(__name__)

if __name__ == "__main__":
    log.info("======================== Start =========================")         

    cfx_data = []
    
    with open('cfx-data.csv', newline='') as File:  
        reader = csv.reader(File, delimiter='\t')
        for row in reader:
            try:
                row[0] = int(row[0])
                cfx_data.append(row)
            except:
                pass
    cfx_data.sort(key=lambda x: x[0])

    state = {"state":"down",
             "diff":int(cfx_data[0][2]),
             "time_start":datetime.datetime.strptime(cfx_data[0][1],"%Y-%m-%d %H:%M:%S.%f"),   # down up_5m up down_5m 
             "deadline":0}   # down up_2m up down_2m 

    for j in range(10,79):
        k_up_down = 0.93 #0.85 # 0.80 - 0.99
        k_down_up = 1.19 #.19 # 1.10 = 1.40
        k_price_estimated = 1.1 #.1 # 1.05 - 1.15 На сколько допустимо превысить рассчетную цену доходности.
        time_start_order = 55*60 # 10 - 100
        market_lists = ["EU","EU_N","USA","USA_E"]
        step = 1
        start_balance = 1.0
        nice = Nice(start_balance)

        for i in range(step,len(cfx_data),step):
            diff_now = int(cfx_data[i][2])
            if diff_now == 0:
                log.error(f"id={cfx_data[i][0]} difficulty = 0")
                continue #Сложность не может быть равна нулю
            time_now = datetime.datetime.strptime(cfx_data[i][1],"%Y-%m-%d %H:%M:%S.%f") #2021-03-24 19:41:07.198087

            #Разница между двумя раундами очень велика Стоп все ордера
            delta = time_now - datetime.datetime.strptime(cfx_data[i - step][1],"%Y-%m-%d %H:%M:%S.%f")
            if delta.seconds > 1800: 
                log.info(f"{cfx_data[i][0]} delta = {delta.seconds}")
                log.info(f"id={cfx_data[i][0]} Stop All Orders") 
                # price_BTC = max_price * deff / 1000000000000 / 172800
                price_BTC = float(cfx_data[i-step][3]) * int(cfx_data[i-step][2]) / 1000000000000 / 172800
                nice.stop_all_orders(price_BTC)
                state = {"state":"down",
                        "diff":int(cfx_data[i][2]),
                        "time_start":datetime.datetime.strptime(cfx_data[i][1],"%Y-%m-%d %H:%M:%S.%f"),   # down up_5m up down_5m 
                        "deadline":0}   # down up_2m up down_2m 
                log.info(str(state))
                continue

            price_BTC = float(cfx_data[i][3]) * int(cfx_data[i][2]) / 1000000000000 / 172800
            if (state["state"] == "down" or state["state"] == "up") and diff_now > k_down_up * state["diff"]: #Сложность повысиластб
                state["state"] = "up_2m"
                state["time_start"] = time_now
                state["deadline"] = 120 # Действует 120 секунд
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = up_2m")
                log.info(f"id={cfx_data[i][0]} Stop All Orders")
                nice.stop_all_orders(price_BTC)

            if state["state"] == "up_2m": 
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    state["state"] = "up"
                    state["time_start"] = time_now
                    state["deadline"] = time_start_order
                    log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = up")
    
            if (state["state"] == "down" or state["state"] == "up") and diff_now < k_up_down * state["diff"]: #Сложность упала
                state["state"] = "down_2m"
                state["time_start"] = time_now
                state["deadline"] = 120 # Действует 120 секунд
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = down_2m") 
                log.info(f"id={cfx_data[i][0]} Process create orders - stop")

            if state["state"] == "down_2m": 
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    state["state"] = "down"
                    state["time_start"] = time_now
                    state["deadline"] = 0 # Действует 120 секунд
                    log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = down")

            if state["state"] == "up" and state["deadline"] != 0: #Начинаем выставлять ордера.
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    for k in range(0,len(market_lists)):
                        nice.start_order_market(market_lists[k], diff_now, 
                                                max_profit_price = float(cfx_data[i][3]), 
                                                k_price_estimated = k_price_estimated, 
                                                p_001 = float(cfx_data[i][4 + k]), 
                                                p_005 = float(cfx_data[i][8 + k]), 
                                                p_010 = float(cfx_data[i][12 + k]), 
                                                p_050 = float(cfx_data[i][16 + k]), 
                                                p_100 = float(cfx_data[i][20 + k]), 
                                                max_limit_TH_s = float(cfx_data[i][24 + k]))
                    if len(nice.orders) == 4:
                        log.info(f"id={cfx_data[i][0]} Process create orders - stop. order count == 4")
                        state["deadline"] = 0 #Если выставлены ордера на всех рынках то хватит выставлять

            # Всё время проверяем выставленые ордера и если есть более выгодеый - переустанавливаем
            # if len(nice.orders) != 0: #как то неэфективно получилось 
            #     for k in range(0,len(market_lists)):
            #         nice.start_order_market(market_lists[k], diff_now, 
            #                                 max_profit_price = float(cfx_data[i][3]), 
            #                                 k_price_estimated = k_price_estimated, 
            #                                 p_001 = float(cfx_data[i][4 + k]), 
            #                                 p_005 = float(cfx_data[i][8 + k]), 
            #                                 p_010 = float(cfx_data[i][12 + k]), 
            #                                 p_050 = float(cfx_data[i][16 + k]), 
            #                                 p_100 = float(cfx_data[i][20 + k]), 
            #                                 max_limit_TH_s = float(cfx_data[i][24 + k]),
            #                                 reorder=True,
            #                                 course = price_BTC,
            #                                 k_percrnt=90)

            # if ((state["state"] == "up") and # Проверяем и перевыставляем ордера
            #     (((state["deadline"] != 0) and (time_now < state["time_start"] + datetime.timedelta(seconds=state["deadline"]))) or
            #     (state["deadline"] == 0))) or (state["state"] == "down"): #Начинаем выставлять ордера.
            #     if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]): 
            #         pass   
            
            nice.mine(diff_now, delta.seconds)

            if diff_now != state["diff"]:
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now}")
                state["diff"] = diff_now
        nice.stop_all_orders(float(cfx_data[-1][3]) * int(cfx_data[-1][2]) / 1000000000000 / 172800)

        p = 100 * (nice.balance_BTC - nice.start_balance_BTC)/nice.start_balance_BTC
        if p > 0:
            log.warning(f"j = {j} start={nice.start_balance_BTC:2.8f} end={nice.balance_BTC:2.8f} percent = {p:3.3f}%")
        else:
            log.error(f"j = {j} start={nice.start_balance_BTC:2.8f} end={nice.balance_BTC:2.8f} percent = {p:3.3f}%")