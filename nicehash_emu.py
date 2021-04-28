import logger, config
log = logger.get_logger(__name__)

class Order(object):
    def __init__(self, market:str, price_BTC_TH_day, limit_TH_s, amount_BTC):
        """Constructor"""
        self.market = market
        self.price_BTC_TH_day = price_BTC_TH_day
        self.limit_TH_s = limit_TH_s
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

    def exchange(self, course:float):
        self.amount_BTC = self.amount_BTC + course * self.amount_CFX
        self.amount_CFX = 0

class Nice(object):
    def __init__(self, balance_BTC):
        """Constructor"""
        self.balance_BTC = balance_BTC
        self.balance_BTC_prev = balance_BTC
        self.orders = []

    def market_is_present_in_orders(self, market):
        result = False
        for order in self.orders:
            if order.market == market:
                result = True
                break
        return result

    def start_order_one(self, market, price_BTC_TH_day, limit_TH_s, amount_BTC):
        if self.balance_BTC == 0:
            return False
        if amount_BTC > self.balance_BTC:
            amount_BTC = self.balance_BTC
        if not self.market_is_present_in_orders(market):
            self.orders.append( Order(market, price_BTC_TH_day, limit_TH_s, amount_BTC))
            self.balance_BTC = self.balance_BTC - amount_BTC
            return True
        return False

    def start_order_market(self, market:str, diff:int, max_profit_price:float, k_price_estimated:float, p_001:float, p_005:float, 
                           p_010:float, p_050:float, p_100:float, max_limit_TH_s:float):

        def line_u(x1,x2,y1,y2,y):
            x = x1 + (x2 - x1) * (y - y1) /(y2 - y1)
            return x

        if self.market_is_present_in_orders(market):
            return False

        #Определить максимальнуб цену
        max_price = max_profit_price * k_price_estimated
        #Определить масимальную мощьность limit_TH_s
        limit_TH_s = 0
        if max_price < p_001:
            return False
        if max_price <= p_005:  
            limit_TH_s = line_u(0.001,0.005,p_001,p_005,max_price)
        if max_price > p_005 and max_price <= p_010:  
            limit_TH_s = line_u(0.005,0.010,p_005,p_010,max_price)
        if max_price > p_010 and max_price <= p_050:  
            limit_TH_s = line_u(0.010,0.050,p_010,p_050,max_price)
        if max_price > p_050 and max_price <= p_100:  
            limit_TH_s = line_u(0.050,0.100,p_050,p_100,max_price)
        if max_price > p_100 and p_100 != 0:  
            limit_TH_s = 0.100

        #Посчитать количество BTC на час
        #Выставить ордер на 3 часа через start_order_one
        pass

    def mine(self, diff:int, time_s:float):
        for order in self.orders:
            order.mine(diff,time_s)

    def stop_all_orders(self, course:float):
        for order in self.orders:
            order.exchange(course)
            self.balance_BTC = self.balance_BTC + order.amount_BTC / config.commission_nicehash
        self.orders.clear()
        p = 100 * (self.balance_BTC - self.balance_BTC_prev)/self.balance_BTC_prev
        self.balance_BTC_prev = self.balance_BTC_prev
        if p > 0:
            log.warning(f"percent = {p:3.2f}%")
        else:
            log.error(f"percent = {p:3.2f}%")

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

    nice.start_order_one("EU", 1.4, 0.05, 0.08)
    nice.start_order_one("USA", 1.4, 0.002, 0.025)
    log.info(f"4 BTC = {nice.balance_BTC}")
    for _ in range(3600*24):
        nice.mine(2254080980003,1)
    nice.stop_all_orders(0.00001831)
    log.info(f"5 BTC = {nice.balance_BTC}")

