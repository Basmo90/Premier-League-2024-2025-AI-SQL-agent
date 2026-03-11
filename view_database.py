#!/usr/bin/env python3
"""
Simple database viewer for Premier League data
Usage: python view_database.py
"""

import sqlite3
import pandas as pd

def view_tables():
    conn = sqlite3.connect('pl_data.db')
    
    print("🏟️  PREMIER LEAGUE DATABASE VIEWER")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. View sample player stats (top 10)")
        print("2. View sample team stats (all teams)")
        print("3. View player info (top 10)")
        print("4. Search for specific player")
        print("5. Search for specific team")
        print("6. Custom SQL query")
        print("7. Exit")
        
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == '1':
            df = pd.read_sql("SELECT player_name, Goals, Assists, pass_accuracy, XG FROM datasets_player_stats_2024_2025_season_csv WHERE Goals > 0 ORDER BY Goals DESC LIMIT 10", conn)
            print("\n📊 TOP 10 GOAL SCORERS:")
            print(df.to_string(index=False))
            
        elif choice == '2':
            df = pd.read_sql("SELECT club_name, Goals, 'Goals Conceded', cross_accuracy, long_pass_accuracy FROM datasets_club_stats_2024_season_club_stats_csv ORDER BY Goals DESC", conn)
            print("\n⚽ ALL TEAM STATS:")
            print(df.to_string(index=False))
            
        elif choice == '3':
            df = pd.read_sql("SELECT player_name, player_club, player_position, player_country FROM datasets_premier_player_info_csv LIMIT 10", conn)
            print("\n👤 PLAYER PROFILES (Top 10):")
            print(df.to_string(index=False))
            
        elif choice == '4':
            player = input("Enter player name (partial match): ")
            df = pd.read_sql(f"SELECT * FROM datasets_player_stats_2024_2025_season_csv WHERE player_name LIKE '%{player}%'", conn)
            if not df.empty:
                print(f"\n🔍 RESULTS FOR '{player}':")
                print(df.to_string(index=False))
            else:
                print(f"❌ No players found matching '{player}'")
                
        elif choice == '5':
            team = input("Enter team name (partial match): ")
            df = pd.read_sql(f"SELECT * FROM datasets_club_stats_2024_season_club_stats_csv WHERE club_name LIKE '%{team}%'", conn)
            if not df.empty:
                print(f"\n🔍 RESULTS FOR '{team}':")
                print(df.to_string(index=False))
            else:
                print(f"❌ No teams found matching '{team}'")
                
        elif choice == '6':
            query = input("Enter SQL query: ")
            try:
                df = pd.read_sql(query, conn)
                print("\n📋 QUERY RESULTS:")
                print(df.to_string(index=False))
            except Exception as e:
                print(f"❌ Error: {e}")
                
        elif choice == '7':
            break
        else:
            print("❌ Invalid choice. Please enter 1-7.")
    
    conn.close()
    print("\n👋 Goodbye!")

if __name__ == "__main__":
    view_tables()