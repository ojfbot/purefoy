#!/usr/bin/env python3
"""
Colored CLI reporting for forum coverage.

Generates test-coverage-style reports with colors and progress bars.
"""

from __future__ import annotations

from typing import Any

from .coverage import CoverageReport


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def get_coverage_color(percent: float) -> str:
    """Get color based on coverage percentage."""
    if percent >= 90:
        return Colors.BRIGHT_GREEN
    elif percent >= 70:
        return Colors.GREEN
    elif percent >= 50:
        return Colors.YELLOW
    elif percent >= 25:
        return Colors.BRIGHT_RED
    else:
        return Colors.RED


def format_percent(percent: float, show_color: bool = True) -> str:
    """Format percentage with color."""
    if not show_color:
        return f"{percent:5.1f}%"

    color = get_coverage_color(percent)
    return f"{color}{percent:5.1f}%{Colors.RESET}"


def draw_progress_bar(percent: float, width: int = 30) -> str:
    """Draw a colored progress bar."""
    filled = int((percent / 100) * width)
    empty = width - filled

    color = get_coverage_color(percent)

    bar = f"{color}{'█' * filled}{Colors.DIM}{'░' * empty}{Colors.RESET}"
    return bar


def print_header(title: str):
    """Print a styled header."""
    line = "=" * 80
    print(f"\n{Colors.BOLD}{Colors.CYAN}{line}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title:^80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{line}{Colors.RESET}\n")


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}━━━ {title} {Colors.DIM}{'━' * (75 - len(title))}{Colors.RESET}")


def print_coverage_report(report: CoverageReport, delta: dict[str, Any] | None = None):
    """Print a comprehensive coverage report with colors."""

    print_header("DEAKINS FORUMS COVERAGE REPORT")

    # Overall statistics
    print(f"{Colors.BOLD}Timestamp:{Colors.RESET} {report.timestamp}")
    print(f"{Colors.BOLD}Overall Coverage:{Colors.RESET} {format_percent(report.overall_coverage_percent)}")
    print()

    # Summary stats
    print(
        f"  {Colors.BOLD}Forums:{Colors.RESET}        {Colors.BRIGHT_GREEN}{report.forums_covered}{Colors.RESET}/{report.total_forums}"
    )
    print(
        f"  {Colors.BOLD}Topics:{Colors.RESET}        {Colors.BRIGHT_GREEN}{report.topics_scraped:,}{Colors.RESET}/{report.total_topics:,}"
    )
    print(f"  {Colors.BOLD}Posts:{Colors.RESET}         {Colors.BRIGHT_GREEN}{report.total_posts:,}{Colors.RESET}")

    # Show delta if available
    if delta and delta.get("new_posts", 0) > 0:
        print(f"\n  {Colors.BRIGHT_YELLOW}📈 This Run:{Colors.RESET}")
        print(
            f"     {Colors.GREEN}+{delta['new_topics']:,}{Colors.RESET} topics, {Colors.GREEN}+{delta['new_posts']:,}{Colors.RESET} posts"
        )
        if delta["coverage_increase"] > 0:
            print(f"     Coverage increased by {Colors.GREEN}+{delta['coverage_increase']:.1f}%{Colors.RESET}")

    # Forum-by-forum coverage
    print_section("Forum Coverage")

    # Table header
    print(f"  {Colors.BOLD}{'Forum':<25} {'Progress':<35} {'Topics':<15} {'Posts':<10}{Colors.RESET}")
    print(f"  {Colors.DIM}{'-' * 90}{Colors.RESET}")

    # Sort forums by coverage
    sorted_forums = sorted(report.forums.values(), key=lambda f: f.coverage_percent, reverse=True)

    for forum in sorted_forums:
        # Forum name
        forum_name = forum.forum_name[:24]

        # Progress bar
        bar = draw_progress_bar(forum.coverage_percent, width=25)
        percent = format_percent(forum.coverage_percent)

        # Topics
        topics_str = f"{forum.topics_scraped:>4}/{forum.total_topics_available:<4}"

        # Posts
        posts_str = f"{forum.posts_scraped:>6,}"

        # Delta indicator
        delta_str = ""
        if delta and forum.forum_slug in delta.get("forum_deltas", {}):
            forum_delta = delta["forum_deltas"][forum.forum_slug]
            if forum_delta["new_topics"] > 0:
                delta_str = f" {Colors.GREEN}(+{forum_delta['new_topics']}){Colors.RESET}"

        print(f"  {forum_name:<25} {bar} {percent}  {topics_str:<15} {posts_str:<10}{delta_str}")

    # Query coverage
    if report.queries:
        print_section("Research Query Coverage")

        # Table header
        print(f"  {Colors.BOLD}{'Query':<40} {'Status':<12} {'Posts':<10} {'Notes':<30}{Colors.RESET}")
        print(f"  {Colors.DIM}{'-' * 100}{Colors.RESET}")

        for query in report.queries.values():
            query_name = query.query_name[:39]

            if query.coverage_complete:
                status = f"{Colors.BRIGHT_GREEN}✓ Complete{Colors.RESET}"
            else:
                status = f"{Colors.YELLOW}⚠ Partial{Colors.RESET} "

            posts = f"{query.posts_matching:>6}"
            notes = query.notes[:28]

            print(f"  {query_name:<40} {status:<21} {posts:<10} {notes}")

    # Footer with legend
    print(
        f"\n{Colors.DIM}Legend: {Colors.RED}< 25%{Colors.RESET} {Colors.BRIGHT_RED}25-50%{Colors.RESET} {Colors.YELLOW}50-70%{Colors.RESET} {Colors.GREEN}70-90%{Colors.RESET} {Colors.BRIGHT_GREEN}>= 90%{Colors.RESET}"
    )
    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}\n")


def print_summary_table(report: CoverageReport):
    """Print a compact summary table."""
    print(f"\n{Colors.BOLD}COVERAGE SUMMARY{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")

    for forum in sorted(report.forums.values(), key=lambda f: f.forum_slug):
        pct = format_percent(forum.coverage_percent)
        bar = draw_progress_bar(forum.coverage_percent, width=20)
        print(f"  {forum.forum_slug:20} {bar} {pct} ({forum.topics_scraped}/{forum.total_topics_available} topics)")

    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")
    overall_pct = format_percent(report.overall_coverage_percent)
    print(
        f"  {Colors.BOLD}OVERALL{Colors.RESET:13} {draw_progress_bar(report.overall_coverage_percent, width=20)} {overall_pct}"
    )
    print()


def print_recommendations(report: CoverageReport):
    """Print recommendations for next scraping operations."""
    print_section("Recommended Next Actions")

    incomplete_forums = [f for f in report.forums.values() if not f.is_complete]

    if not incomplete_forums:
        print(f"  {Colors.BRIGHT_GREEN}✓ All forums fully scraped!{Colors.RESET}")
        return

    # Sort by least coverage first
    incomplete_forums.sort(key=lambda f: f.coverage_percent)

    print(f"  {Colors.YELLOW}Incomplete forums that need more scraping:{Colors.RESET}\n")

    for forum in incomplete_forums[:5]:  # Top 5
        remaining = forum.total_topics_available - forum.topics_scraped

        print(f"    • {Colors.BOLD}{forum.forum_name}{Colors.RESET}")
        print(
            f"      Coverage: {format_percent(forum.coverage_percent)} ({forum.topics_scraped}/{forum.total_topics_available} topics)"
        )
        print(f"      {Colors.CYAN}→ Scrape {remaining} more topics{Colors.RESET}")
        print()


def print_quick_stats(report: CoverageReport):
    """Print quick one-line stats."""
    pct = format_percent(report.overall_coverage_percent)
    print(
        f"{Colors.BOLD}Coverage:{Colors.RESET} {pct} | "
        f"{Colors.BOLD}Forums:{Colors.RESET} {report.forums_covered}/{report.total_forums} | "
        f"{Colors.BOLD}Topics:{Colors.RESET} {report.topics_scraped:,}/{report.total_topics:,} | "
        f"{Colors.BOLD}Posts:{Colors.RESET} {report.total_posts:,}"
    )
