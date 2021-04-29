import logger, config
log = logger.get_logger(__name__)

def get_limit(x1,x2,y1,y2,y):
    if y1 == 0:
        y1 = 100000 * y
    if y2 == 0:
        y2 = 100000 * y
    if y2 != y1:
        x = x1 + (x2 - x1) * (y - y1) /(y2 - y1)
    else:
        if y2 < y:
            x = x2
        else:
            x = 0
    if x < x1 or x > x2:
        x = 0                
    return x

class Order(object):
    def __init__(self, market:str, diff:int, price_BTC_TH_day, limit_TH_s, amount_BTC):
        """Constructor"""
        self.market = market
        self.diff = diff
        self.price_BTC_TH_day = price_BTC_TH_day
        self.limit_TH_s = limit_TH_s
        self.start_BTC =  amount_BTC
        self.amount_BTC = config.commission_nicehash * amount_BTC - 0.00001 #3,8 процента комиссия nicehash
        self.amount_CFX = 0.0

    def is_market(self, market:str):
        return self.market == market

    def mine(self, diff:int, time_s:float):
        if self.amount_BTC == 0:
            return
        delta_CFX = 172800 * (1000000000000 * self.limit_TH_s / (diff)) * (time_s / (24 * 60 * 60))
        delta_BTC = (self.price_BTC_TH_day / (24 * 60 * 60)) * self.limit_TH_s * time_s
        if delta_BTC > self.amount_BTC:
            delta_CFX = delta_CFX * self.amount_BTC / delta_BTC
            delta_BTC = self.amount_BTC
        self.amount_CFX = self.amount_CFX + delta_CFX
        self.amount_BTC = self.amount_BTC - delta_BTC
        # log.info(f"{self.market} BTC = {self.amount_BTC} CFX = {self.amount_CFX}")

    def stop_and_exchange(self, course:float):
        self.amount_BTC = self.amount_BTC / config.commission_nicehash + course * self.amount_CFX
        self.limit_TH_s = 0
        self.amount_CFX = 0

    def __del__(self): #Перед удалением обязательно вызвать stop_and_exchange(self, course:float):
        # p = 100 * (self.amount_BTC - self.start_BTC)/self.start_BTC
        # if p > 0:
        #     log.warning(f"Stop order {self.market} start={self.start_BTC:2.8f} end={self.amount_BTC:2.8f} percent = {p:3.3f}%")
        # else:
        #     log.error(f"Stop order {self.market} start={self.start_BTC:2.8f} end={self.amount_BTC:2.8f} percent = {p:3.3f}%")
        pass

class Nice(object):
    def __init__(self, balance_BTC):
        """Constructor"""
        self.balance_BTC = balance_BTC
        self.start_balance_BTC = balance_BTC
        self.minimum_balance_BTC = balance_BTC
        self.balance_CFX = 0
        # self.balance_BTC_prev = balance_BTC
        self.orders = []

    def market_is_present_in_orders(self, market):
        result = False
        for order in self.orders:
            if order.market == market:
                result = True
                break
        return result

    def start_order_one(self, market, diff, price_BTC_TH_day, limit_TH_s, amount_BTC, max_profit_price):
        if self.balance_BTC == 0:
            return False
        if amount_BTC > self.balance_BTC:
            amount_BTC = self.balance_BTC
        if not self.market_is_present_in_orders(market):
            self.orders.append( Order(market, diff, price_BTC_TH_day, limit_TH_s, amount_BTC))
            self.balance_BTC = self.balance_BTC - amount_BTC
            log.info(f"Start order = {market} max_profit_price = {max_profit_price} price_BTC_TH_day={price_BTC_TH_day} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
            return True
        return False

    def stop_order_n(self, n:int, course:float):
        self.orders[n].stop_and_exchange(course)
        self.balance_BTC = self.balance_BTC + self.orders[n].amount_BTC
        self.orders.pop(n)

    def stop_order(self, market:str, course:float):
        for k in range(len(self.orders)):
            if self.orders[k].market == market: #Оцениваем новый ордер. Цена на k_percrnt меньше - перевыставляем               
                self.stop_order_n(k,course)
                break

    def start_order_market(self, market:str, diff:int, max_profit_price:float, k_price_estimated:float, p_001:float, p_005:float, 
                           p_010:float, p_050:float, p_100:float, max_limit_TH_s:float, reorder = False, course:float = 0, k_percrnt = 5):
        present = self.market_is_present_in_orders(market) 
        if (present and not reorder) or (not present and reorder): #Если ордер уже есть то не выставлять
            return False

        #Определить максимальнуб цену
        max_price = max_profit_price * k_price_estimated

        #Определить масимальную мощьность limit_TH_s
        limit_TH_s = 0
        limit_TH_s = max([limit_TH_s, get_limit(0.001,0.005,p_001,p_005,max_price)])
        limit_TH_s = max([limit_TH_s, get_limit(0.005,0.010,p_005,p_010,max_price)])
        limit_TH_s = max([limit_TH_s, get_limit(0.010,0.050,p_010,p_050,max_price)])
        limit_TH_s = max([limit_TH_s, get_limit(0.050,0.100,p_050,p_100,max_price)])
        if max_price > p_100 and p_100 != 0:  
            limit_TH_s = 0.100
        if limit_TH_s > 0.99 * max_limit_TH_s:
            limit_TH_s = 0.99 * max_limit_TH_s
        limit_TH_s = round(limit_TH_s - 0.0005, 3)
        if limit_TH_s < 0.001:
            return False

        #Посчитать количество BTC на час amount_BTC = power * price_power * 3 / 24
        amount_BTC = round(limit_TH_s * max_price * 24 / 24 + 0.0005, 3)
        
        if not reorder: #Выставить новый ордер start_order_one
            self.start_order_one(market, diff, max_price, limit_TH_s, amount_BTC, max_profit_price)
        else:
            flag_start = False
            for k in range(len(self.orders)):
                order = self.orders[k]
                if order.market == market: #Оцениваем новый ордер. Цена на k_percrnt меньше - перевыставляем
                    # if (((1 + (k_percrnt//10) /100) * max_price < order.price_BTC_TH_day) and 
                    #     # (100 * (order.start_BTC - order.amount_BTC) / order.start_BTC > 2 * (k_percrnt % 10)) and
                    #     (1.05 * amount_BTC > order.amount_BTC)):
                    k1 = 1 + (k_percrnt/100)                   
                    if max_price * amount_BTC > k1 * order.price_BTC_TH_day * order.amount_BTC:
                        flag_start = True
                        # log.warning(f"Reorder stop {market} price_BTC_TH_day = {order.price_BTC_TH_day} limit_TH_s = {order.limit_TH_s} amount_BTC = {order.amount_BTC}")
                        self.stop_order_n(k,course)
                        break
            if flag_start:
                # log.warning(f"Reorder start price_BTC_TH_day = {max_price} limit_TH_s = {limit_TH_s} amount_BTC = {amount_BTC}")
                self.start_order_one(market, diff, max_price, limit_TH_s, amount_BTC, max_profit_price)

    def check_and_stop(self, diff:float, k_diff_order_stop : float, course:float):
        k = 0
        while k < len(self.orders):
            if diff > k_diff_order_stop * self.orders[k].diff:
                self.stop_order_n(k , course)
            else: 
                k += 1
        

    def mine(self, diff:int, time_s:float):
        if self.balance_BTC < self.minimum_balance_BTC:
            self.minimum_balance_BTC = self.balance_BTC
        for order in self.orders:
            order.mine(diff,time_s)

    def stop_all_orders(self, course:float):
        while len(self.orders) != 0:
            self.stop_order_n(0, course)

if __name__ == "__main__":
    nice = Nice(0.1)

    log.info(f"1 BTC = {nice.balance_BTC}")
    nice.start_order_market("EU", 2786714681928, 1.51114716813653, 1.1, 1.6, 1.6462, 1.6868, 2.15, 0, 0.0591)
    nice.start_order_market("USA",2786714681928, 1.51114716813653, 1.1, 1.5, 1.5462, 1.5868, 1.75, 1.9, 0.0991)

    log.info(f"2 BTC = {nice.balance_BTC}")
    for _ in range(3600*24):
        nice.mine(1852417174249,1)
    nice.stop_all_orders(0.00001831)
    log.info(f"3 BTC = {nice.balance_BTC}")

    nice.start_order_market("EU", 2786714681928, 1.51114716813653, 1.1, 1.6, 1.6462, 0, 2.15, 0, 0.0591)
    nice.start_order_market("USA",2786714681928, 1.51114716813653, 1.1, 0, 1.5462, 1.5868, 1.75, 1.9, 0.0991)
    log.info(f"4 BTC = {nice.balance_BTC}")
    for _ in range(3600*24):
        nice.mine(2254080980003,1)
    nice.stop_all_orders(0.00001831)
    log.info(f"5 BTC = {nice.balance_BTC}")

