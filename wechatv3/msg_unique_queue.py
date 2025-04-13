import queue
import threading

class DedupQueue(queue.Queue):
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        self._item_set = set()
        self._lock = threading.Lock()

    def put(self, item, block=True, timeout=None):
        with self._lock:
            if item in self._item_set:
                return  # 去重，不入队
            self._item_set.add(item)
        super().put(item, block, timeout)

    def get(self, block=True, timeout=None):
        item = super().get(block, timeout)
        with self._lock:
            self._item_set.discard(item)
        return item

    def clear(self):
        """清空队列"""
        with self.mutex:
            self.queue.clear()
        with self._lock:
            self._item_set.clear()

    def __contains__(self, item):
        with self._lock:
            return item in self._item_set

    def snapshot(self) -> list:
        """线程安全地获取队列当前所有元素的快照"""
        with self.mutex:
            return list(self.queue)