# 同花顺官方库放置目录

把从同花顺官方获取的 **THS.py** 和 **THS.dll** 放在本目录下。

之后在 `data_source/ths_source.py` 中即可这样导入：

```python
import THS
```

## 如何获取

- 联系同花顺（iFinD）获取 Python 接口开发包；
- 或使用你已有的同花顺客户端配套的算法交易/数据接口文件。

## 注意

- 需要把本目录加入 Python 的模块搜索路径（`data_source/ths_source.py` 中已做说明）；
- 同花顺客户端需本地安装并登录，程序运行时会调用其数据服务。
