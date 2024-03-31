from asyncio import AbstractEventLoop, AbstractEventLoopPolicy, Task
import asyncio
from collections import deque
import logging
from queue import LifoQueue
from threading import Thread
import threading
from typing import Deque, Set

import aiohttp
from antfyutils.data_obj import CfgDcNtfy, SendNtfyMessage
from format import seconds_to_time, 秒转时间


class PushUtils:
    cfg: CfgDcNtfy
    pool: asyncio.Queue
    thread: Thread
    eventloop: AbstractEventLoop
    cn: bool
    info: bool
    # lock: threading.RLock
    def __init__(self, cfg: CfgDcNtfy, queue_size=30, cn=False, info=True) -> None:
        self.cfg = cfg
        self.pool = asyncio.Queue(maxsize=queue_size)
        self.thread = None
        self.cn = cn
        self.info = info
        pass
    async def __run_loop(self):
        msg = await self.pool.get()
        if not msg:
            return
        s = set()
        s.add(asyncio.create_task(self.__push(msg)))
        s.add(self.__run_loop())
        await asyncio.gather(*s)
        pass
    def __run_thread(self):
        self.eventloop = asyncio.new_event_loop()
        self.eventloop.run_until_complete(self.__run_loop())
        pass
    def startServer(self):
        self.thread = Thread(name="Push Thread", target=self.__run_thread)
        self.thread.start()
        pass
    def stopServer(self):
        if self.thread:
            self.eventloop.run_in_executor(self.pool.put(None))
            self.eventloop.run_in_executor(self.thread.join())
        pass
    async def push(self, msg:SendNtfyMessage):
        await asyncio.wait_for(self.pool.put(msg), timeout=10)
    async def __push(self, msg: SendNtfyMessage):
        if not msg.topic:
            msg.topic = self.cfg.topic
        count = 0
        while True:
            count += 1
            if count >=3:
                return
            async with aiohttp.ClientSession(headers={'User-Agent': 'antfyutils/1.0 aiohttp python', "Authorization": f"Bearer {self.cfg.token}"}) as session:
                try:
                    async with session.post(f"{self.cfg.url}", json=msg.to_dict()) as req:
                        ret =await req.read()
                        if ret:
                            logging.debug(ret.decode())
                        if self.cn:
                            if self.info:
                                logging.info(f"消息推送成功！{msg.to_json(ensure_ascii=False)}")
                            else:
                                logging.debug(f"消息推送成功！{msg.to_json(ensure_ascii=False)}")

                        else:
                            if self.info:
                                logging.info(f"Message push success! {msg.to_json(ensure_ascii=False)}")
                            else:
                                logging.debug(f"Message push success! {msg.to_json(ensure_ascii=False)}")
                        pass
                    break
                except aiohttp.ClientConnectorError as e:
                    logging.exception(e)
                    wait = count * 10
                    if self.cn:
                        logging.error(f"推送失败！尝试重新推送,{秒转时间(wait)}秒后再试。")
                    else:
                        logging.error(f"Push failed! Attempting to push again. Retry after {seconds_to_time(wait)}.")
                    await asyncio.sleep(wait)
                    pass
    pass