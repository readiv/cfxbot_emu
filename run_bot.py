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


    with open('log-order.csv', 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=',')
        row = ["id","diff","max_price","p_n_EU","p_o_EU","p_n_EU_N","p_o_EU_N","p_n_USA","p_o_USA","p_n_USA_E","p_o_USA_E"]
        csvwriter.writerow(row)
        
        k_up_down = 0.93 #0.85 # 0.80 - 0.99
        k_down_up = 1.1 #1.19 #.19 # 1.10 = 1.40
        k_diff_order_stop = 1.0
        k_price_order_stop = 1.08
        k_avg = 1.05
        k_price_estimated = 1.04 #.1 # 1.05 - 1.15 На сколько допустимо превысить рассчетную цену доходности.
        k_mypower_to_nh = 1.1
        time_start_order = 30 # 10 - 100
        market_lists = ["EU","EU_N","USA","USA_E"]
        step = 1
        start_balance = 1.0
        nice = Nice(start_balance)

        for i in range(step,len(cfx_data),step):
            row = [i,int(cfx_data[i][2])/1500000000000,float(cfx_data[i][3])]

            diff_now = int(cfx_data[i][2])
            if diff_now == 0:
                log.error(f"id={cfx_data[i][0]} difficulty = 0")
                continue #Сложность не может быть равна нулю
            time_now = datetime.datetime.strptime(cfx_data[i][1],"%Y-%m-%d %H:%M:%S.%f") #2021-03-24 19:41:07.198087

            #Разница между двумя раундами очень велика Стоп все ордера
            delta = time_now - datetime.datetime.strptime(cfx_data[i - step][1],"%Y-%m-%d %H:%M:%S.%f")
            # print(delta.seconds + delta.microseconds/1000000)
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

            for k in range(0,len(market_lists)): #Попытка учесть влияние своих ордеров на рынок
                order = nice.get_order(market_lists[k])
                if order is not None:
                    cfx_data[i][ 4 + k] = k_mypower_to_nh * float(cfx_data[i][ 4 + k])
                    cfx_data[i][ 8 + k] = k_mypower_to_nh * float(cfx_data[i][ 8 + k]) 
                    cfx_data[i][12 + k] = k_mypower_to_nh * float(cfx_data[i][12 + k]) 
                    cfx_data[i][16 + k] = k_mypower_to_nh * float(cfx_data[i][16 + k]) 
                    cfx_data[i][20 + k] = k_mypower_to_nh * float(cfx_data[i][20 + k]) 
                    
            price_BTC = float(cfx_data[i][3]) * int(cfx_data[i][2]) / 1000000000000 / 172800
            if price_BTC == 0:
                continue

            if (state["state"] == "down" or state["state"] == "up") and diff_now > k_down_up * state["diff"]: #Сложность повысиластб
                state["state"] = "up_2m"
                state["time_start"] = time_now
                state["deadline"] = config.time_2m # Действует секунд
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = up_2m")
                # log.info(f"id={cfx_data[i][0]} Stop All Orders")
                # nice.stop_all_orders(price_BTC)

            if state["state"] == "up_2m": 
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    state["state"] = "up"
                    state["time_start"] = time_now
                    state["deadline"] = time_start_order
                    # k_avg = 1.0 + j2/100
                    log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = up")
    
            if (state["state"] == "down" or state["state"] == "up") and diff_now < k_up_down * state["diff"]: #Сложность упала
                state["state"] = "down_2m"
                state["time_start"] = time_now
                state["deadline"] = config.time_2m # Действует 120 секунд
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = down_2m") 
                log.info(f"id={cfx_data[i][0]} Process create orders - stop")

            if state["state"] == "down_2m": 
                if time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                    state["state"] = "down"
                    state["time_start"] = time_now
                    state["deadline"] = 0 # Действует 120 секунд
                    log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now} state = down")

            if state["state"] == "up" and time_now < state["time_start"] + datetime.timedelta(seconds=state["deadline"]):
                for k in range(0,len(market_lists)): 
                    p_avg_001 = nice.avg.get(k) 
                    if p_avg_001 != -1:         
                        if float(cfx_data[i][4 + k]) > k_avg * p_avg_001:
                            state["deadline"] = (time_now - state["time_start"]).seconds
                    nice.avg.add(k, float(cfx_data[i][4 + k]))

            if state["state"] == "up" and time_now > state["time_start"] + datetime.timedelta(seconds=state["deadline"]): 
                for k in range(0,len(market_lists)): #Начинаем выставлять ордера.
                    if float(cfx_data[i][ 4 + k]) !=0:
                        nice.start_order_market(market_lists[k], diff_now, #Если ордер уже есть то не выставлять его
                                                max_profit_price = float(cfx_data[i][3]), 
                                                k_price_estimated = k_price_estimated, 
                                                p_001 = float(cfx_data[i][ 4 + k]), 
                                                p_005 = float(cfx_data[i][ 8 + k]), 
                                                p_010 = float(cfx_data[i][12 + k]), 
                                                p_050 = float(cfx_data[i][16 + k]), 
                                                p_100 = float(cfx_data[i][20 + k]), 
                                                max_limit_TH_s = float(cfx_data[i][24 + k]))
                    # if len(nice.orders) == 4:
                    #     log.info(f"id={cfx_data[i][0]} Process create orders - stop. order count == 4")
                    #     state["deadline"] = 0 #Если выставлены ордера на всех рынках то хватит выставлять
            # Майним
            
            nice.mine(diff_now, delta.seconds + delta.microseconds/1000000)
            nice.check_and_add_amount() #Пополняем ордера
            nice.check_and_stop(price_BTC)
            nice.exchange_CFX(price_BTC, config.amount_CFX_for_exchange)

            for k in range(0,len(market_lists)):
                if float(cfx_data[i][ 4 + k]) == 0:
                    cfx_data[i][ 4 + k] = cfx_data[i][3]
                row.append(float(cfx_data[i][ 4 + k]))
                row.append(nice.get_price_order(market_lists[k]))

            # Всё время проверяем выставленые ордера и если есть более выгодеый - переустанавливаем
            if len(nice.orders) != 0: #как то неэфективно получилось 
                for k in range(0,len(market_lists)):
                    if float(cfx_data[i][ 4 + k]) !=0:
                        nice.start_order_market(market_lists[k], diff_now, 
                                                max_profit_price = float(cfx_data[i][3]), 
                                                k_price_estimated = k_price_estimated, 
                                                p_001 = float(cfx_data[i][ 4 + k]), 
                                                p_005 = float(cfx_data[i][ 8 + k]), 
                                                p_010 = float(cfx_data[i][12 + k]), 
                                                p_050 = float(cfx_data[i][16 + k]), 
                                                p_100 = float(cfx_data[i][20 + k]), 
                                                max_limit_TH_s = float(cfx_data[i][24 + k]),
                                                reorder=True,
                                                course = price_BTC,
                                                k_percrnt=1.0) 
            
            # Проверяем все ордера и если какой-то невыгодный по diff - стопаем его
            # if ((state["state"] == "up" and time_now <= state["time_start"] + datetime.timedelta(seconds=state["deadline"])) or
            #     (state["state"] == "down")):
            #     nice.check_and_stop_diff(float(cfx_data[i][2]), k_diff_order_stop, price_BTC)

            # Проверяем все ордера и если какой-то невыгодный по цене - стопаем его
            if ((state["state"] == "up" and time_now <= state["time_start"] + datetime.timedelta(seconds=state["deadline"])) or
                (state["state"] == "down")):
                nice.check_and_stop_price(float(cfx_data[i][3]), k_price_order_stop, price_BTC)

            if diff_now != state["diff"]:
                log.info(f"id={cfx_data[i][0]} diff_old = {state['diff']} diff_new = {diff_now}")
                state["diff"] = diff_now

            csvwriter.writerow(row)
        # Завершение программы       
        nice.stop_all_orders(float(cfx_data[-1][3]) * int(cfx_data[-1][2]) / 1000000000000 / 172800)
        nice.exchange_CFX(price_BTC, 0)

        p = 100 * (nice.balance_BTC - nice.start_balance_BTC)/nice.start_balance_BTC
        if p > 0:
            log.warning(f"minumum_BTC={start_balance - nice.minimum_balance_BTC:2.8f} |end=|{nice.balance_BTC:2.8f}|percent = {p:3.3f}%")
        else:
            log.error(f"minumum_BTC={start_balance - nice.minimum_balance_BTC:2.8f} |end=|{nice.balance_BTC:2.8f}|percent = {p:3.3f}%")