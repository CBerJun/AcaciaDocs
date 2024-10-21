Acacia 文档
===================================

欢迎！这是 Acacia 的官方文档。

**Acacia**\ （*uh kay shuh*）是一门运行在 Minecraft 基岩版的编程语言。Minecraft 的命令较为复杂、很长、且难以维护，Acacia 便是为了解决这个问题的——它也是用来控制 Minecraft 来实现各类从小到大的项目的，但是它使用更加便捷的语法设计，使得开发者能够专注在\ **项目逻辑**\ 上，而不是苦恼于各种麻烦的\ **技术难题**\ 。

.. note::

    此项目仍然在进行开发，如果遇到 Bug 或者有任何建议，欢迎在 `Github <https://github.com/CBerJun/AcaciaMC>`_ 提出！

.. warning::

    此文档目前几乎只是一个“实验品”，其中只有几页的信息并且这些信息有可能是过时的。在 Acacia 编译器本身准备好被“正式发布”之前，我们才会正式开始完善此文档。

测试::

    if_
    else
    0x111ffg
    /*
    aa ${
        bb + {"x": 10, "y": -25}
    }a
    */
    1.290
    /\${}\\
    "\u00a7"
    "%0aa%{1}1%{kw}%%"
        /say aaa ${xxx}
    "\#(green, bold)"
    "numbers 1 2 3 :="
    deff
    entity foo o o
    lint
    interface spam/ham:
    interface aaa11-bb_1.2()
    interface "xxx":
    interface if:
    interface222
    swap(1)
    Alice and Bob
    or xor

.. module:: foo

    ``foo`` 模块。

    .. function:: bar()

        这是 ``bar``。

    .. function:: spam()
        :type: inline

        可以引用 :mod:`foo` 里的其他内容 :fn:`bar`\ 。
        当然也可以引用最上层的 :fn:`test_function`\ 。

.. function:: test_function(arg1, arg2)

    测试函数，引用 :fn:`foo.spam`\ 。
    引用 :fn:`~foo.spam`\ ，不带模块名。

.. function:: f1(const arg1: int, &arg2 = x) -> const foo.bar
    :type: inline

    f1，这是一个参数 :arg:`arg1`\ 。

.. function:: f2(x: int = 0xBeeF, y = "foo\")bar", z = {1, 2, 3}) -> int
    :type: const

    f2，参数 :arg:`x`\ 。

.. function:: f3(x=1+2+f2(), y=False)

    f3

文档大纲
--------

.. toctree::
    :maxdepth: 2

    tutorial/index.rst
    language/index.rst
