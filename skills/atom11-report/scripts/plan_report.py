#!/usr/bin/env python3
"""Validate an Atom11 report profile and print the deterministic run plan.

Usage:
    python3 plan_report.py --profile profile.json [--today YYYY-MM-DD] [--json]

The plan lists the modules to run in report order, the Atom11 analysis or
dataset behind each, the exact parameters to pass, the resolved reporting
window, and the output filename. A profile that fails validation exits with
status 2 and a message meant to be relayed verbatim.

Standard library only (Python 3.9+).
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import re
import sys
from typing import Any

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

PROFILE_VERSION = 1

# --------------------------------------------------------------------------
# Module registry — must agree with references/module-catalog.md (tested).
# window: dated | as-of | dated_28 | dated_weekly
# --------------------------------------------------------------------------
MODULES: dict[str, dict[str, Any]] = {
    # Headline
    'performance': dict(kind='recipe', source='account_report', window='dated',
                        intent='account report', group='headline',
                        defaults={'report_mode': 'full', 'excluded_sections': [],
                                  'metric_profile': 'overview_dashboard',
                                  'wasted_spend_min_clicks': 5,
                                  'wasted_spend_click_operator': 'gte'}),
    'dsp_performance': dict(kind='recipe', source='dsp_account_report', window='dated',
                            intent='dsp account report', group='dsp', dsp=True,
                            defaults={}),
    'blended_overview': dict(kind='recipe', source='blended_ppc_dsp_overview', window='dated',
                             intent='blended ppc dsp tacos', group='headline', dsp=True,
                             defaults={}),
    # Trend and mix
    'tacos_trend': dict(kind='recipe', source='tacos_trend', window='dated',
                        intent='tacos trend weekly', group='trend', defaults={}),
    'targeting_mix': dict(kind='recipe', source='targeting_mix', window='dated',
                          intent='targeting type mix auto vs manual', group='trend',
                          defaults={'mode': 'targeting_type'}),
    'term_mix': dict(kind='recipe', source='term_mix', window='dated',
                     intent='branded competitor term mix', group='trend', defaults={}),
    'placements': dict(kind='dataset', source='ads_placement', window='dated',
                       intent='placement performance top of search', group='trend',
                       defaults={}, query_hint='grain ["placement"]; optional ads_placement_summary top campaigns by spend'),
    'placement_movement': dict(kind='dataset', source='ads_placement_period_comparison', window='dated',
                               intent='placement period comparison', group='trend',
                               defaults={}, query_hint='grain ["placement"]; current/previous/delta columns from schema'),
    'dayparting': dict(kind='dataset', source='ads_hourly_performance', window='dated_28',
                       intent='hourly performance hour of day dayparting', group='trend',
                       defaults={}, query_hint='grain ["hour_of_day"] (24 rows) and optionally ["day_of_week","hour_of_day"] (168 rows); page_size 200'),
    'audiences': dict(kind='recipe', source='audience_period_comparison', window='dated',
                      intent='audience current vs previous comparison', group='trend',
                      defaults={'limit': 20}),
    # Campaigns
    'campaign_review': dict(kind='recipe', source='campaign_performance_review', window='dated',
                            intent='campaign performance review target acos movement', group='campaigns',
                            defaults={'rank_metric': 'ad_sales_attributed',
                                      'comparison_metric': 'ad_sales_attributed',
                                      'comparison_window_days': 0, 'limit': 10,
                                      'missing_target_policy': 'unavailable',
                                      'meaningful_change_percent': 20}),
    'campaign_movers': dict(kind='recipe', source='wow_campaign_movers', window='dated',
                            intent='week over week campaign movers', group='campaigns',
                            defaults={'attribution_window_days': 14, 'limit': 10}),
    'campaign_health': dict(kind='recipe', source='campaign_health', window='dated',
                            intent='campaign performance with status and budget', group='campaigns',
                            defaults={'attribution_window_days': 14, 'limit': 25}),
    'campaign_wasted_spend': dict(kind='recipe', source='campaign_wasted_spend', window='dated',
                                  intent='campaign wasted spend zero orders', group='campaigns',
                                  defaults={'attribution_window_days': 14, 'min_clicks': 1, 'limit': 10}),
    'serving_health': dict(kind='recipe', source='campaign_not_serving', window='as-of',
                           intent='campaigns not serving', group='campaigns',
                           defaults={'limit': 20}),
    'rca': dict(kind='recipe', source='entity_drop_rca', window='dated',
                intent='performance drop root cause drilldown', group='campaigns',
                defaults={'limit': 20}, required=['entity_type', 'entity_value']),
    # Search terms and keywords
    'top_search_terms': dict(kind='recipe', source='top_search_terms', window='dated',
                             intent='top search terms by sales', group='search',
                             defaults={'search_term_scope': 'SP', 'qualification_grain': 'dashboard_row',
                                       'rank_by': 'sales', 'sales_operator': 'gt', 'min_sales': 0, 'limit': 10}),
    'wasted_spend_terms': dict(kind='recipe', source='wasted_spend', window='dated',
                               intent='search terms wasted spend zero orders', group='search',
                               defaults={'min_clicks': 5, 'click_operator': 'gte', 'zero_outcome': 'orders',
                                         'detail_policy': 'bounded', 'limit': 10}),
    'harvest_terms': dict(kind='recipe', source='harvest_candidates', window='dated',
                          intent='search term harvest candidates', group='search',
                          defaults={'attribution_window_days': 14, 'min_orders': 2, 'min_clicks': 1,
                                    'targeted_terms': 'include', 'limit': 25}),
    'keyword_bid_efficiency': dict(kind='recipe', source='keyword_bid_efficiency', window='dated',
                                   intent='keyword bid efficiency cpc below bid', group='search',
                                   defaults={'limit': 10}),
    'keywords_paused': dict(kind='recipe', source='exact_keywords_paused_recently', window='dated',
                            intent='exact keywords paused recently', group='search',
                            defaults={'limit': 20}),
    'sqp': dict(kind='dataset', source='search_query_performance', window='dated_weekly',
                intent='search query performance brand analytics', group='search',
                defaults={}, query_hint='grain by search query (and ASIN when asked); sort by volume or purchases; page_size 25'),
    'sqp_movement': dict(kind='dataset', source='search_query_performance_comparison', window='dated_weekly',
                         intent='search query performance comparison share drop', group='search',
                         defaults={}, query_hint='current vs previous share columns; sort by purchase-share delta; page_size 25'),
    # Products
    'top_products': dict(kind='recipe', source='top_advertised_products', window='dated',
                         intent='top advertised products asin', group='products',
                         defaults={'rank_metric': 'ad_spend', 'limit': 20}),
    'asin_scorecard': dict(kind='recipe', source='asin_daily', window='dated',
                           intent='asin ads vs retail vs inventory', group='products',
                           defaults={'limit': 20}),
    'label_products': dict(kind='recipe', source='label_product_performance', window='dated',
                           intent='label product performance', group='products',
                           defaults={'limit': 500}, required_any=['label_name', 'label_ref']),
    'auto_manual_mismatch': dict(kind='recipe', source='advertised_product_auto_manual_mismatch', window='dated',
                                 intent='auto vs manual acos mismatch', group='products', defaults={}),
    'abc_classification': dict(kind='dataset', source='ads_asin_abc_performance', window='dated',
                               intent='asin abc classification', group='products',
                               defaults={}, query_hint='product grain with band column; sort by retail sales; page_size 50'),
    'portfolios': dict(kind='dataset', source='ads_portfolio_performance', window='dated',
                       intent='portfolio performance', group='products',
                       defaults={}, query_hint='portfolio grain; sort by spend; page_size 50'),
    'labels': dict(kind='dataset', source='ads_label_performance', window='dated',
                   intent='label performance', group='products',
                   defaults={}, query_hint='one explicit label_kind filter per query (campaign or ASIN labels); label grain; sort by spend; page_size 50'),
    # Inventory
    'restock': dict(kind='recipe', source='restock_priority', window='as-of',
                    intent='restock priority low stock', group='inventory',
                    defaults={'max_days_of_cover': 30, 'reorder_target_days': 15, 'limit': 15}),
    'inventory_exposure': dict(kind='recipe', source='campaign_out_of_stock_products + ad_group_low_stock_products',
                               window='as-of', intent='campaigns advertising out of stock products',
                               group='inventory', defaults={'max_days_of_cover': 30},
                               note='two analyses: campaign_out_of_stock_products takes no parameters; ad_group_low_stock_products takes max_days_of_cover'),
    'ineligible_products': dict(kind='recipe', source='ineligible_ad_products', window='as-of',
                                intent='ineligible ad products not serving', group='inventory',
                                defaults={'limit': 100}),
    # Digital shelf
    'digital_shelf_bsr': dict(kind='recipe', source='digital_shelf_bsr_decline', window='dated',
                              intent='bsr decline tracked asins', group='shelf',
                              defaults={'limit': 20}),
    'digital_shelf_rank': dict(kind='dataset', source='digital_shelf_search_rank', window='dated',
                               intent='keyword search rank organic sponsored', group='shelf',
                               defaults={}, query_hint='keyword + ASIN grain, organic and sponsored positions, latest dates; page_size 50'),
    'catalog_snapshot': dict(kind='dataset', source='product_catalog', window='as-of',
                             intent='product catalog latest price rating availability', group='shelf',
                             defaults={}, query_hint='product grain: title, latest price, availability, rating, reviews, BSR; page_size 50'),
    # Recommendations and automation
    'recommendations': dict(kind='recipe', source='current_recommendations', window='dated',
                            intent='current recommendations report', group='recs',
                            defaults={'section': 'all', 'limit': 25}),
    'suggested_bids': dict(kind='recipe', source='current_recommendations', window='as-of',
                           intent='current suggested bids', group='recs',
                           defaults={'section': 'suggested_bids', 'limit': 25}),
    'automation_activity': dict(kind='dataset', source='automation_activity', window='dated',
                                intent='automation rule activity history', group='recs',
                                defaults={}, query_hint='timestamp, action kind, object name, previous/new value, action_source, status, reverted; sort time desc; page_size 50'),
    'goals': dict(kind='recipe', source='goal_performance', window='dated',
                  intent='goal performance', group='campaigns',
                  defaults={'attribution_window_days': 14}),
    # DSP
    'dsp_movers': dict(kind='recipe', source='dsp_campaign_movers', window='dated',
                       intent='dsp order movers', group='dsp', dsp=True, defaults={'limit': 10}),
    'dsp_weekday_weekend': dict(kind='recipe', source='dsp_weekday_weekend', window='dated',
                                intent='dsp weekday weekend', group='dsp', dsp=True, defaults={}),
    'dsp_line_items': dict(kind='dataset', source='(discover: DSP line item / creative / audience dataset)',
                           window='dated', intent='DSP line item performance', group='dsp', dsp=True,
                           defaults={}, query_hint='one bounded query sorted by cost; page_size 25'),
}

SECTION_ORDER = ['headline', 'trend', 'campaigns', 'search', 'products', 'inventory', 'shelf', 'recs', 'dsp']

REPORT_TYPES: dict[str, dict[str, Any]] = {
    'weekly': dict(core=['performance', 'campaign_movers', 'campaign_review', 'top_search_terms',
                         'wasted_spend_terms', 'restock', 'recommendations'],
                   default_window='last_7_complete_days'),
    'monthly': dict(core=['performance', 'tacos_trend', 'targeting_mix', 'term_mix', 'campaign_review',
                          'top_products', 'top_search_terms', 'wasted_spend_terms', 'harvest_terms',
                          'restock', 'recommendations'],
                    default_window='last_complete_month'),
    'account': dict(core=['performance'], default_window='last_7_complete_days'),
    'campaigns': dict(core=['campaign_review', 'campaign_movers', 'campaign_wasted_spend', 'campaign_health'],
                      default_window='last_7_complete_days'),
    'search_terms': dict(core=['top_search_terms', 'wasted_spend_terms', 'harvest_terms'],
                         default_window='last_14_complete_days'),
    'products': dict(core=['top_products', 'asin_scorecard'], default_window='last_30_complete_days'),
    'inventory': dict(core=['restock', 'inventory_exposure'], default_window=None),
    'dsp': dict(core=['dsp_performance', 'dsp_movers'], default_window='last_7_complete_days', dsp=True),
    'blended': dict(core=['blended_overview', 'performance', 'dsp_performance'],
                    default_window='last_7_complete_days', dsp=True),
    'goals': dict(core=['goals'], default_window='last_30_complete_days'),
    'keywords_bids': dict(core=['keyword_bid_efficiency', 'suggested_bids', 'keywords_paused'],
                          default_window='last_14_complete_days'),
    'placements': dict(core=['placements'], default_window='last_14_complete_days'),
    'dayparting': dict(core=['dayparting'], default_window='last_14_complete_days'),
    'sqp': dict(core=['sqp', 'sqp_movement'], default_window='last_30_complete_days'),
    'portfolios_labels': dict(core=['portfolios', 'labels'], default_window='last_30_complete_days'),
    'digital_shelf': dict(core=['digital_shelf_bsr', 'digital_shelf_rank', 'catalog_snapshot'],
                          default_window='last_30_complete_days'),
    'automation': dict(core=['automation_activity', 'keywords_paused'], default_window='last_14_complete_days'),
    'serving': dict(core=['serving_health', 'ineligible_products'], default_window=None),
    'recommendations': dict(core=['recommendations', 'suggested_bids'], default_window='last_7_complete_days'),
    'rca': dict(core=['rca'], default_window='last_14_complete_days'),
}

WINDOW_KINDS = {'last_7_complete_days', 'last_14_complete_days', 'last_30_complete_days',
                'last_complete_week', 'last_complete_month', 'month_to_date'}
FRESHNESS_POLICIES = {'shift_to_complete', 'deliver_partial', 'strict'}

# profile.options key -> {module_id: param_name}
OPTION_MAP: dict[str, dict[str, str]] = {
    'wasted_spend_min_clicks': {'performance': 'wasted_spend_min_clicks', 'wasted_spend_terms': 'min_clicks'},
    'wasted_spend_click_operator': {'performance': 'wasted_spend_click_operator', 'wasted_spend_terms': 'click_operator'},
    'campaign_limit': {'campaign_review': 'limit', 'campaign_movers': 'limit',
                       'campaign_wasted_spend': 'limit', 'campaign_health': 'limit'},
    'search_term_limit': {'top_search_terms': 'limit', 'wasted_spend_terms': 'limit', 'harvest_terms': 'limit'},
    'product_limit': {'top_products': 'limit', 'asin_scorecard': 'limit'},
    'max_days_of_cover': {'restock': 'max_days_of_cover', 'inventory_exposure': 'max_days_of_cover'},
    'reorder_target_days': {'restock': 'reorder_target_days'},
    'attribution_window_days': {'campaign_movers': 'attribution_window_days',
                                'campaign_health': 'attribution_window_days',
                                'campaign_wasted_spend': 'attribution_window_days',
                                'harvest_terms': 'attribution_window_days',
                                'goals': 'attribution_window_days'},
    'rank_metric': {'campaign_review': 'rank_metric'},
    'missing_target_policy': {'campaign_review': 'missing_target_policy'},
    'report_mode': {'performance': 'report_mode'},
    'excluded_sections': {'performance': 'excluded_sections'},
}
KNOWN_OPTION_KEYS = set(OPTION_MAP) | {'targets', 'module_params'}

PARAM_CHOICES: dict[tuple[str, str], set] = {
    ('performance', 'report_mode'): {'full', 'summary', 'ads_only', 'retail_only'},
    ('performance', 'metric_profile'): {'overview_dashboard', 'amazon_14d', 'sp_7d'},
    ('performance', 'wasted_spend_click_operator'): {'gt', 'gte'},
    ('wasted_spend_terms', 'click_operator'): {'gt', 'gte'},
    ('wasted_spend_terms', 'zero_outcome'): {'orders', 'sales'},
    ('campaign_review', 'rank_metric'): {'ad_sales_attributed', 'ad_spend'},
    ('campaign_review', 'comparison_metric'): {'ad_sales_attributed', 'ad_spend'},
    ('campaign_review', 'missing_target_policy'): {'unavailable', 'account_average'},
    ('top_search_terms', 'search_term_scope'): {'SP', 'SP_SB'},
    ('top_search_terms', 'qualification_grain'): {'dashboard_row', 'term'},
    ('top_search_terms', 'rank_by'): {'sales', 'orders', 'spend', 'clicks', 'cvr', 'acos', 'roas', 'ctr'},
    ('top_search_terms', 'sales_operator'): {'gt', 'gte'},
    ('harvest_terms', 'targeted_terms'): {'include', 'exclude'},
    ('targeting_mix', 'mode'): {'targeting_type', 'auto_manual'},
    ('recommendations', 'section'): {'all', 'cards', 'advertising', 'inventory', 'suggested_bids'},
    ('rca', 'entity_type'): {'asin', 'campaign', 'portfolio'},
}
ATTRIBUTION_CHOICES = {7, 14}


class ProfileError(ValueError):
    pass


# --------------------------------------------------------------------------
# Window resolution
# --------------------------------------------------------------------------
def _today_in(tz_name: str | None, override: str | None) -> dt.date:
    if override:
        return dt.date.fromisoformat(override)
    if tz_name and ZoneInfo is not None:
        try:
            return dt.datetime.now(ZoneInfo(tz_name)).date()
        except Exception as exc:  # noqa: BLE001
            raise ProfileError(f'account.timezone {tz_name!r} is not a valid IANA timezone') from exc
    return dt.date.today()


def resolve_window(window: Any, today: dt.date) -> tuple[dt.date, dt.date, str]:
    """Return (start, end, label) for a cadence window, ending yesterday."""
    yesterday = today - dt.timedelta(days=1)
    if isinstance(window, dict):
        if window.get('kind') == 'last_complete_days':
            days = window.get('days')
            if not isinstance(days, int) or days < 1 or days > 365:
                raise ProfileError('cadence.window.days must be an integer between 1 and 365')
            return yesterday - dt.timedelta(days=days - 1), yesterday, f'last {days} complete days'
        if 'start' in window and 'end' in window:
            start, end = dt.date.fromisoformat(window['start']), dt.date.fromisoformat(window['end'])
            if end < start:
                raise ProfileError('cadence.window.end is before start')
            if end > yesterday:
                raise ProfileError('cadence.window.end must be a complete day (yesterday or earlier)')
            return start, end, 'explicit window'
        raise ProfileError('cadence.window object must be {"kind":"last_complete_days","days":N} or {"start","end"}')
    if window == 'last_7_complete_days':
        return yesterday - dt.timedelta(days=6), yesterday, 'last 7 complete days'
    if window == 'last_14_complete_days':
        return yesterday - dt.timedelta(days=13), yesterday, 'last 14 complete days'
    if window == 'last_30_complete_days':
        return yesterday - dt.timedelta(days=29), yesterday, 'last 30 complete days'
    if window == 'last_complete_week':
        # Most recent Sunday that is <= yesterday; Monday = weekday 0.
        offset = (yesterday.weekday() - 6) % 7
        sunday = yesterday - dt.timedelta(days=offset)
        return sunday - dt.timedelta(days=6), sunday, 'last complete Monday–Sunday week'
    if window == 'last_complete_month':
        first_this = today.replace(day=1)
        last_prev = first_this - dt.timedelta(days=1)
        return last_prev.replace(day=1), last_prev, 'last complete calendar month'
    if window == 'month_to_date':
        first = today.replace(day=1)
        if yesterday < first:
            raise ProfileError('month_to_date needs at least one complete day in the current month')
        return first, yesterday, 'month to date'
    raise ProfileError(f'cadence.window {window!r} is not a known window rule')


# --------------------------------------------------------------------------
# Validation and planning
# --------------------------------------------------------------------------
def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'account'


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ProfileError(message)


def build_plan(profile: dict, today_override: str | None = None) -> dict:
    _require(isinstance(profile, dict), 'profile must be a JSON object')
    _require(profile.get('profile_version') == PROFILE_VERSION,
             f'profile_version must be {PROFILE_VERSION}')
    account = profile.get('account') or {}
    _require(isinstance(account.get('display_name'), str) and account['display_name'].strip(),
             'account.display_name is required (the exact Atom11 display name)')
    system = account.get('system', 'ads_profile')
    _require(system in {'ads_profile', 'dsp_advertiser'},
             'account.system must be ads_profile or dsp_advertiser')
    request = profile.get('request')
    _require(isinstance(request, str) and request.strip(),
             'request is required: the standing request line copied into user_question')

    report_type = profile.get('report_type')
    _require(report_type in REPORT_TYPES,
             f'report_type must be one of: {", ".join(sorted(REPORT_TYPES))}')
    rtype = REPORT_TYPES[report_type]

    dsp = profile.get('dsp')
    dsp_name = None
    if dsp:
        _require(isinstance(dsp, dict) and isinstance(dsp.get('display_name'), str) and dsp['display_name'].strip(),
                 'dsp.display_name must be the confirmed DSP advertiser display name')
        dsp_name = dsp['display_name'].strip()
    if rtype.get('dsp'):
        _require(dsp_name is not None or system == 'dsp_advertiser',
                 f'report_type {report_type} needs dsp.display_name (a confirmed DSP advertiser) or a dsp_advertiser account')

    cadence = profile.get('cadence') or {}
    window_rule = cadence.get('window') or rtype.get('default_window')
    freshness_policy = cadence.get('freshness_policy', 'shift_to_complete')
    _require(freshness_policy in FRESHNESS_POLICIES,
             f'cadence.freshness_policy must be one of: {", ".join(sorted(FRESHNESS_POLICIES))}')
    frequency = cadence.get('frequency', 'one-off')
    _require(frequency in {'weekly', 'monthly', 'one-off', 'daily'},
             'cadence.frequency must be weekly, monthly, daily or one-off')

    modules_cfg = profile.get('modules') or {}
    include = list(modules_cfg.get('include') or [])
    exclude = list(modules_cfg.get('exclude') or [])
    for mid in include + exclude:
        _require(mid in MODULES, f'unknown module id {mid!r} in modules.include/exclude')
    if dsp and isinstance(dsp.get('modules'), list):
        for mid in dsp['modules']:
            _require(mid in MODULES and MODULES[mid].get('dsp'), f'dsp.modules entry {mid!r} is not a DSP module')
            include.append(mid)
    selected = [m for m in rtype['core'] if m not in exclude]
    for mid in include:
        if mid not in selected:
            selected.append(mid)
    _require(selected, 'no modules left to run after exclusions')
    for mid in selected:
        if MODULES[mid].get('dsp'):
            _require(dsp_name is not None or system == 'dsp_advertiser',
                     f'module {mid} needs dsp.display_name (a confirmed DSP advertiser)')

    options = profile.get('options') or {}
    unknown = sorted(set(options) - KNOWN_OPTION_KEYS)
    module_params = options.get('module_params') or {}
    for mid in module_params:
        _require(mid in MODULES, f'options.module_params has unknown module id {mid!r}')

    # Window
    today = _today_in(account.get('timezone'), today_override)
    needs_window = any(MODULES[m]['window'] != 'as-of' for m in selected)
    window = None
    if needs_window:
        _require(window_rule is not None, 'cadence.window is required because a dated module is selected')
        start, end, label = resolve_window(window_rule, today)
        window = {'start': start.isoformat(), 'end': end.isoformat(), 'label': label,
                  'days': (end - start).days + 1}

    # Per-module parameters
    ordered = sorted(selected, key=lambda m: (SECTION_ORDER.index(MODULES[m]['group']), selected.index(m)))
    plan_modules = []
    for mid in ordered:
        spec = MODULES[mid]
        params: dict[str, Any] = dict(spec['defaults'])
        applied: dict[str, str] = {}
        for opt_key, targets in OPTION_MAP.items():
            if opt_key in options and mid in targets and options[opt_key] is not None:
                params[targets[mid]] = options[opt_key]
                applied[targets[mid]] = f'options.{opt_key}'
        for key, value in (module_params.get(mid) or {}).items():
            params[key] = value
            applied[key] = f'options.module_params.{mid}'
        for key, value in list(params.items()):
            if (mid, key) in PARAM_CHOICES:
                _require(value in PARAM_CHOICES[(mid, key)],
                         f'{mid}.{key}={value!r} is not one of {sorted(PARAM_CHOICES[(mid, key)])}')
            if key == 'attribution_window_days':
                _require(value in ATTRIBUTION_CHOICES, f'{mid}.attribution_window_days must be 7 or 14')
            if key in {'limit', 'min_clicks', 'min_orders', 'max_days_of_cover', 'reorder_target_days',
                       'wasted_spend_min_clicks', 'meaningful_change_percent', 'comparison_window_days'}:
                _require(isinstance(value, int) and value >= 0, f'{mid}.{key} must be a non-negative integer')
        for key in spec.get('required', []):
            _require(key in params, f'module {mid} requires options.module_params.{mid}.{key}')
        if spec.get('required_any'):
            _require(any(k in params for k in spec['required_any']),
                     f'module {mid} requires one of {spec["required_any"]} in options.module_params.{mid}')
        entry: dict[str, Any] = {
            'module': mid, 'kind': spec['kind'], 'source': spec['source'], 'intent': spec['intent'],
            'window_kind': spec['window'], 'params': params, 'param_sources': applied,
        }
        if spec['window'] == 'as-of':
            entry['window'] = None
        elif spec['window'] == 'dated_28' and window and window['days'] > 28:
            end = dt.date.fromisoformat(window['end'])
            entry['window'] = {'start': (end - dt.timedelta(days=27)).isoformat(), 'end': window['end']}
            entry['note'] = 'window clamped to the last 28 days of the report window (hourly dataset limit); say so in the section'
        else:
            entry['window'] = {'start': window['start'], 'end': window['end']} if window else None
        if spec['kind'] == 'recipe' and entry['window']:
            entry['params'] = {'date_range': entry['window'], **params}
        if spec.get('dsp'):
            entry['scope'] = 'dsp_advertiser'
            if mid in {'dsp_performance', 'blended_overview'} and dsp_name:
                entry['params']['confirmed_dsp_display_name'] = dsp_name
            if mid == 'blended_overview':
                entry['related_scope_ids'] = {'dsp': '<dsp scope_id from get_my_data_scopes>'}
                entry['scope'] = 'ads_profile (+ related dsp)'
        else:
            entry['scope'] = system
        if spec.get('query_hint'):
            entry['query_hint'] = spec['query_hint']
        if spec.get('note'):
            entry['note'] = spec['note']
        plan_modules.append(entry)

    output = profile.get('output') or {}
    prefix = output.get('filename_prefix') or f'atom11-{report_type}-{_slug(account["display_name"])}'
    end_token = window['end'] if window else today.isoformat()
    filename = f'{_slug(prefix)}-{end_token}.html'

    return {
        'profile_name': profile.get('name') or f'{account["display_name"]} {report_type}',
        'client': profile.get('client'),
        'prepared_for': profile.get('prepared_for'),
        'request': request,
        'account': {'display_name': account['display_name'].strip(), 'system': system,
                    'timezone': account.get('timezone')},
        'dsp_display_name': dsp_name,
        'report_type': report_type,
        'cadence': {'frequency': frequency, 'window_rule': window_rule, 'freshness_policy': freshness_policy,
                    'run_day': cadence.get('run_day'), 'run_time': cadence.get('run_time')},
        'today': today.isoformat(),
        'window': window,
        'targets': (options.get('targets') or {}),
        'focus': profile.get('focus') or [],
        'modules': plan_modules,
        'output_filename': filename,
        'warnings': ([f'unknown options ignored: {", ".join(unknown)}'] if unknown else []),
    }


def format_plan(plan: dict) -> str:
    lines = [f"Report plan — {plan['profile_name']}",
             f"  account      : {plan['account']['display_name']} ({plan['account']['system']})"]
    if plan['dsp_display_name']:
        lines.append(f"  dsp          : {plan['dsp_display_name']} (confirmed display name)")
    lines.append(f"  report type  : {plan['report_type']}  cadence: {plan['cadence']['frequency']}  "
                 f"freshness: {plan['cadence']['freshness_policy']}")
    if plan['window']:
        w = plan['window']
        lines.append(f"  window       : {w['start']} → {w['end']} ({w['days']} days, {w['label']}; today {plan['today']})")
    else:
        lines.append(f"  window       : none (as-of modules only; today {plan['today']})")
    lines.append(f"  user_question: {plan['request']}")
    if plan['targets']:
        lines.append(f"  targets      : {json.dumps(plan['targets'])} (narrative only; never passed as parameters)")
    lines.append(f"  output file  : {plan['output_filename']}")
    lines.append('  modules (in report order):')
    for i, m in enumerate(plan['modules'], 1):
        src = f"{m['kind']} {m['source']}"
        lines.append(f"   {i:2d}. {m['module']:<22} {src}")
        lines.append(f"       intent : {m['intent']}   scope: {m['scope']}")
        if m['window']:
            lines.append(f"       window : {m['window']['start']} → {m['window']['end']}")
        else:
            lines.append('       window : as-of (no date_range)')
        params = {k: v for k, v in m['params'].items() if k != 'date_range'}
        if params:
            lines.append(f"       params : {json.dumps(params)}")
        if m.get('related_scope_ids'):
            lines.append(f"       related_scope_ids: {json.dumps(m['related_scope_ids'])}")
        if m.get('query_hint'):
            lines.append(f"       query  : read get_data_schema first; {m['query_hint']}")
        if m.get('note'):
            lines.append(f"       note   : {m['note']}")
    for w in plan['warnings']:
        lines.append(f'  warning: {w}')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--profile', required=True, help='path to the report profile JSON')
    parser.add_argument('--today', help='override today (YYYY-MM-DD) for deterministic planning')
    parser.add_argument('--json', action='store_true', help='print the plan as JSON instead of text')
    args = parser.parse_args(argv)
    try:
        with open(args.profile, encoding='utf-8') as fh:
            profile = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f'profile error: cannot read {args.profile}: {exc}', file=sys.stderr)
        return 2
    try:
        plan = build_plan(profile, args.today)
    except ProfileError as exc:
        print(f'profile error: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(plan, indent=2) if args.json else format_plan(plan))
    return 0


if __name__ == '__main__':
    sys.exit(main())
