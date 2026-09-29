"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import shipment as router_shipment
from app.routers import temp_monitor as router_temp_monitor
from app.routers import vehicle as router_vehicle
from app.routers import driver as router_driver
from app.routers import dispatch as router_dispatch
from app.routers import cold_storage as router_cold_storage
from app.routers import loading as router_loading
from app.routers import alert as router_alert
from app.routers import route as router_route
from app.routers import reefer_unit as router_reefer_unit
from app.routers import fuel as router_fuel
from app.routers import delivery as router_delivery
from app.routers import break_chain as router_break_chain
from app.routers import dock as router_dock
from app.routers import package as router_package
from app.routers import toll as router_toll
from app.routers import sanitation as router_sanitation
from app.routers import contract as router_contract
from app.routers import insurance as router_insurance

ROUTERS = [router_shipment, router_temp_monitor, router_vehicle, router_driver, router_dispatch, router_cold_storage, router_loading, router_alert, router_route, router_reefer_unit, router_fuel, router_delivery, router_break_chain, router_dock, router_package, router_toll, router_sanitation, router_contract, router_insurance]
