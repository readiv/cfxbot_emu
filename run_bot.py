#!/usr/bin/env python3
import logger, os, datetime, config
os.chdir(logger.get_script_dir())

log = logger.get_logger(__name__)
log_date = datetime.datetime.now().strftime(config.log_name_template)

def change_log_date():
    global log
    log.info(f"name log file changed {datetime.datetime.now().strftime(config.log_name_template)}")
    
    for hdlr in log.handlers[:]:  # remove all old handlers
        log.removeHandler(hdlr)
    log = logger.get_logger(__name__)

    # bonwin_uid2key.change_log_date()

if __name__ == "__main__":
    log.info("======================== Start =========================")
    while True:
        log_date_now = datetime.datetime.now().strftime(config.log_name_template)
        if log_date != log_date_now:
            change_log_date()
            log_date = log_date_now