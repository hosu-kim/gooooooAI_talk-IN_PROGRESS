#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
          ___
      .:::---:::.
    .'--:     :--'.                      ___     ____   ______        __ __  
   /.'   \   /   `.\      ____ _ ____   /   |   /  _/  /_  __/____ _ / // /__
  | /'._ /:::\ _.'\ |    / __ `// __ \ / /| |   / /     / /  / __ `// // //_/
  |/    |:::::|    \|   / /_/ // /_/ // ___ | _/ /     / /  / /_/ // // ,<   
  |:\ .''-:::-''. /:|   \__, / \____//_/  |_|/___/    /_/   \__,_//_//_/|_|  
   \:|    `|`    |:/   /____/                                                
    '.'._.:::._.'.'
      '-:::::::-'

goAI_talk - Football Match Results Q&A Bot
File: interface/cli.py
Author: hosu-kim
Created: 2025-03-14 10:24:15 UTC

Description:
    This module provides the command line interface for the Football Q&A system.
    It handles user input, displays match information, and manages the interaction loop.
"""
import argparse
import sys
import time
from datetime import datetime, timedelta
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# Import fetch_matches from utils.data_fetcher
from utils.data_fetcher import fetch_matches
from api.football_api import FootballAPI
from database.database_manager import DBManager
from llm.qna_engine import QnAEngine

class FootballQnACLI:
    """Command-line interface for the Football Q&A system."""

    def __init__(self, football_api, db_manager, qna_engine, user_location=None, use_test_data=False):
        """
        Initialize the CLI application with required components.
        Sets up the console, database, API, and QnA engine.

        Args:
            football_api: API client for fetching football data.
            db_manager: Database manager for match data.
            qna_engine: QnA engine for processing user questions.
            user_location: Optional user location to personalize data (e.g., "Europe", "Seoul").
            use_test_data: Whether to use test data instead of live API.
        """
        self.console = Console()
        self.db_manager = db_manager
        self.football_api = football_api
        self.qna_engine = qna_engine
        self.user_location = user_location
        self.use_test_data = use_test_data
        self.data_refreshed = False

    def start(self):
        """
        Start the CLI application.
        Display welcome message and enter the main loop.
        """
        self._display_header()

        try:
            self._check_data_freshness()
            self._main_loop()
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Program terminated by user.[/yellow]")
        except Exception as e:
            self.console.print(f"[bold red]Error: {str(e)}[/bold red]")
        finally:
            self.console.print("[green]Thanks for using Football Q&A bot! Goodbye![/green]")

    def _display_header(self):
        """Display the application header and info."""
        self.console.print(Panel.fit(
            "[bold green]Football Matches Q&A Bot[/bold green]\n"
            "[italic]Ask me anything about recent football matches![/italic]",
            border_style="green"
        ))

        current_time = datetime.utcnow()
        self.console.print(f"[dim]Current Date and Time (UTC): {current_time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

        self.console.print(f"\ntype [bold]'help'[/bold] for available commands or [bold]'exit'[/bold] to quit.\n")
        if self.user_location:
            self.console.print(f"[blue]User Location:[/blue] {self.user_location}")
            
        if self.use_test_data:
            self.console.print(f"[yellow]Running in TEST MODE with mock data[/yellow]")

    def _check_data_freshness(self):
        """Check if match data needs to be refreshed from the API."""
        last_update = self.db_manager.get_last_update_time()
        current_time = datetime.utcnow()

        if not last_update or current_time - last_update > timedelta(hours=12):
            self.console.print("[yellow]Match data is outdated. Refreshing from API...[/yellow]")
            self._refresh_data()
        else:
            self.console.print(f"[dim]Using {'test' if self.use_test_data else 'cached'} match data (last updated: {last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC)[/dim]")

    def _refresh_data(self):
        """Refresh match data from the football API."""
        with self.console.status("[bold green]Fetching latest match data...[/bold green]"):
            try:
                yesterday = datetime.utcnow() - timedelta(days=1)
                date_str = yesterday.strftime("%Y-%m-%d")
                
                if self.use_test_data:
                    # Use the imported fetch_matches function for test data
                    matches = fetch_matches(date_str, use_test_data=True)
                    if matches:
                        transformed_matches = []
                        for match in matches:
                            transformed_match = {
                                "date": date_str,
                                "home_team": match["teams"]["home"]["name"],
                                "away_team": match["teams"]["away"]["name"],
                                "home_score": match["goals"]["home"],
                                "away_score": match["goals"]["away"],
                                "league": match["league"]["name"],
                                "fixture_id": match["fixture"]["id"],
                                "goals": []  # Transform goals if needed
                            }
                            transformed_matches.append(transformed_match)
                        matches = transformed_matches
                else:
                    # Use live API
                    if self.user_location:
                        matches = self.football_api.get_matches(date_str, location=self.user_location)
                    else:
                        matches = self.football_api.get_matches(date_str)
                
                if matches:
                    self.db_manager.save_matches(matches)
                    self.data_refreshed = True
                    self.console.print(f"[green]Successfully refreshed data. {len(matches)} matches retrieved.[/green]")
                else:
                    self.console.print("[yellow]No matches found for the specified date.[/yellow]")
                    
            except Exception as e:
                self.console.print(f"[bold red]Failed to refresh data: {str(e)}[/bold red]")

    def _main_loop(self):
        """Main interaction loop for handling user input."""
        while True:
            user_input = Prompt.ask("\n[bold cyan]Ask me about football matches[/bold cyan]")
            user_input = user_input.strip().lower()

            if user_input in ("exit", "quit", "q"):
                break
            elif user_input == "help":
                self._show_help()
            elif user_input in ("refresh", "update"):
                self._refresh_data()
            elif user_input in ("leagues", "competitions"):
                self._show_available_leagues()
            elif user_input == "teams":
                self._show_available_teams()
            elif user_input == "matches":
                self._show_matches_summary()
            elif user_input:
                self._process_question(user_input)

    def _process_question(self, question):
        """
        Process a user's question and display the answer.

        Args:
            question (str): User's football-related question
        """
        self.console.print("[dim]Thinking...[/dim]")

        if not self.data_refreshed:
            self.console.print("[yellow]No data available. Try running with --fetch flag first:[/yellow]")
            self.console.print("python main.py --fetch")
            return

        yesterday = datetime.utcnow() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        matches = self.db_manager.get_matches(date_str)

        if not matches:
            self.console.print("[yellow]No match data available for yesterday. Possible reasons:[/yellow]")
            self.console.print("1. No matches were played yesterday")
            self.console.print("2. API key not configured (.env file)")
            self.console.print("3. Database connection error")
            self.console.print("\nTry refreshing data with: [bold]refresh[/bold] command")
            return

        try:
            with self.console.status("[bold green]Generating answer...[/bold green]"):
                answer = self.qna_engine.get_answer(question, matches)
            self.console.print(Panel(answer, title="[bold]Answer[/bold]", border_style="blue"))
        except Exception as e:
            self.console.print(f"[bold red]Error generating answer: {str(e)}[/bold red]")

    def _show_help(self):
        """Display help information with available commands."""
        help_table = Table(title="Available Commands.")
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description")

        help_table.add_row("help", "Show this help message")
        help_table.add_row("exit, quit, q", "Exit the application")
        help_table.add_row("refresh, update", "Refresh match data from API")
        help_table.add_row("leagues, competitions", "Show available leagues")
        help_table.add_row("teams", "Show available teams")
        help_table.add_row("matches", "Show summary of yesterday's matches")
        help_table.add_row("<question>", "Ask any question about yesterday's matches")

        self.console.print(help_table)
        self.console.print("\n[italic]Example questions:[/italic]")
        self.console.print("  • Who won the Premier League match yesterday?")
        self.console.print("  • Did Manchester United play yesterday?")
        self.console.print("  • How many goals were scored in La Liga?")
        self.console.print("  • Who scored for Arsenal?")

    def _show_available_leagues(self):
        """Display a list of leagues with matches in the database."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        leagues = self.db_manager.get_leagues(date_str)

        if not leagues:
            self.console.print("[yellow]No league data available.[/yellow]")
            return
        
        leagues_table = Table(title="Available Leagues")
        leagues_table.add_column("League", style="cyan")
        leagues_table.add_column("Matches", justify="right")

        for league in leagues:
            leagues_table.add_row(league["name"], str(league["match_count"]))
        
        self.console.print(leagues_table)

    def _show_available_teams(self):
        """Display a list of teams that played in yesterday's matches."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        teams = self.db_manager.get_teams(date_str)

        if not teams:
            self.console.print("[yellow]No team data available.[/yellow]")
            return
        
        teams_table = Table(title="Teams That Played Yesterday")
        teams_table.add_column("Team", style="cyan")
        teams_table.add_column("League", style="green")

        for team in teams:
            teams_table.add_row(team["name"], team["league"])

        self.console.print(teams_table)

    def _show_matches_summary(self):
        """Display a summary of yesterday's matches."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
        matches = self.db_manager.get_matches(date_str)

        if not matches:
            self.console.print("[yellow]No match data available for yesterday.[/yellow]")
            return
        
        matches_table = Table(title=f"Matches Summary ({date_str})")
        matches_table.add_column("League", style="green")
        matches_table.add_column("Home", style="cyan")
        matches_table.add_column("Score", style="bold")
        matches_table.add_column("Away", style="cyan")

        for match in matches:
            matches_table.add_row(
                match["league"],
                match["home_team"],
                f"{match['home_score']} - {match['away_score']}",
                match["away_team"]
            )

        self.console.print(matches_table)

def main():
    """Entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="Football Matches Q&A CLI")
    parser.add_argument("--refresh", action="store_true", help="Force refresh of match data")
    parser.add_argument("--location", type=str, help="Specify your location (e.g., Europe, Seoul)")
    parser.add_argument("--test", action="store_true", help="Use test data instead of real API")
    args = parser.parse_args()

    # Initialize components based on whether we're using test data
    if args.test:
        from utils.test_data import TestFootballAPI, TestDBManager
        football_api = TestFootballAPI()
        db_manager = TestDBManager()
        print("Running with TEST DATA - No API calls will be made")
    else:
        # Regular API and DB manager
        football_api = FootballAPI()
        db_manager = DBManager()

    qna_engine = QnAEngine()

    cli = FootballQnACLI(football_api, db_manager, qna_engine, 
                       user_location=args.location,
                       use_test_data=args.test)

    if args.refresh:
        cli.console.print("[yellow]Forcing data refresh...[/yellow]")
        cli._refresh_data()

    cli.start()

if __name__ == "__main__":
    main()
