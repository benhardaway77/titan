# Import registered backtest runners so @register decorators fire
# when this package is imported (e.g. during `titan promote`).
import titan.backtest.momentum_backtest  # noqa: F401
