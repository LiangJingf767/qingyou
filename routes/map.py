# -*- coding: utf-8 -*-
"""高德地图路由：地理编码 / 逆地理 / POI / 输入提示 / 路径规划。

统一信封：成功 code=0；参数错误 1000；高德调用失败 3000（CODE_EXT_ERROR）。
"""
from flask import Blueprint, request, render_template

from response import ok, bad_request, fail, CODE_EXT_ERROR
from services.amap_service import (
    AmapError, geocode, regeo, search_poi, input_tips, driving,
)
from services.weather_service import daily_forecast, WeatherError

bp = Blueprint("map", __name__, url_prefix="/api/v1")


def _num_arg(name):
    """解析浮点参数，缺省/非法返回 None。"""
    v = request.args.get(name)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _run(fn, *args, **kwargs):
    """统一捕获 AmapError → 3000。"""
    try:
        return ok(fn(*args, **kwargs))
    except AmapError as e:
        return fail(CODE_EXT_ERROR, f"高德服务调用失败：{e}")


@bp.route("/map/geocode", methods=["GET"])
def map_geocode():
    """地理编码 ?address=&city=。"""
    address = (request.args.get("address") or "").strip()
    if not address:
        return bad_request("缺少 address")
    return _run(geocode, address, city=request.args.get("city"))


@bp.route("/map/regeo", methods=["GET"])
def map_regeo():
    """逆地理编码 ?lng=&lat=。"""
    lng, lat = _num_arg("lng"), _num_arg("lat")
    if lng is None or lat is None:
        return bad_request("缺少合法的 lng / lat")
    return _run(regeo, lng, lat)


@bp.route("/map/poi", methods=["GET"])
def map_poi():
    """POI 搜索 ?keywords=&city=&types=&offset=。"""
    keywords = (request.args.get("keywords") or "").strip()
    if not keywords:
        return bad_request("缺少 keywords")
    offset = int(_num_arg("offset") or 10)
    return _run(search_poi, keywords, city=request.args.get("city"),
                types=request.args.get("types"), offset=max(1, min(offset, 25)), page=1)


@bp.route("/map/input_tips", methods=["GET"])
def map_input_tips():
    """输入提示 ?keywords=&city=（目的地搜索联想）。"""
    keywords = (request.args.get("keywords") or "").strip()
    if not keywords:
        return bad_request("缺少 keywords")
    return _run(input_tips, keywords, city=request.args.get("city"))


@bp.route("/map/directions", methods=["GET"])
def map_directions():
    """驾车路径规划 ?origin=lng,lat&destination=lng,lat。"""
    origin = request.args.get("origin")
    destination = request.args.get("destination")
    if not origin or not destination:
        return bad_request("缺少 origin / destination（格式 lng,lat）")
    return _run(driving, origin, destination)


@bp.route("/map/demo", methods=["GET"])
def map_demo():
    """前端地图接入演示页（验证 JS Key + 后端坐标回填联调）。"""
    return render_template("map.html")


@bp.route("/weather", methods=["GET"])
def weather():
    """逐日天气预报 ?city=&days=。失败返回 3000，前端优雅降级。"""
    city = (request.args.get("city") or "").strip()
    days = request.args.get("days")
    if not city:
        return bad_request("缺少 city")
    try:
        return ok(daily_forecast(city, days=int(days) if days else 3))
    except WeatherError as e:
        return fail(CODE_EXT_ERROR, f"天气获取失败：{e}")
