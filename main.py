import csv
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter.ttk import Treeview

from PIL import Image, ImageTk
import sqlite3
import requests
from io import BytesIO
import os
import datetime
import threading
import time

from rapidfuzz.fuzz import imported

# RAWG API Key (replace with your own from rawg.io)
API_KEY = "X"
BASE_URL = "https://api.rawg.io/api/games"


# Database setup with expanded columns
def init_db():
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS games (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      status TEXT,
                      release_date TEXT,
                      rating REAL,
                      image_url TEXT,
                      platform TEXT,
                      genre TEXT,
                      playtime INTEGER DEFAULT 0,
                      notes TEXT,
                      date_added TEXT,
                      date_modified TEXT)''')
    conn.commit()
    conn.close()


# Cache for images
image_cache = {}


def get_cached_image(url, size=(200, 300)):
    if url in image_cache:
        return image_cache[url]

    try:
        response = requests.get(url)
        if response.status_code == 200:
            img_data = Image.open(BytesIO(response.content))
            img_data = img_data.resize(size, Image.LANCZOS)
            img = ImageTk.PhotoImage(img_data)
            image_cache[url] = img
            return img
    except Exception as e:
        print(f"Error loading image: {e}")
    return None


# Save local copies of images for offline use
def save_image_locally(url, game_id):
    if not os.path.exists("game_images"):
        os.makedirs("game_images")

    try:
        response = requests.get(url)
        if response.status_code == 200:
            file_path = f"game_images/{game_id}.jpg"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
    except Exception as e:
        print(f"Error saving image: {e}")
    return None


# Enhanced API fetch with more details
def fetch_game_details(game_name):
    try:
        params = {"key": API_KEY, "search": game_name, "page_size": 10}
        response = requests.get(BASE_URL, params=params)

        if response.status_code == 200:
            data = response.json()
            if "results" in data and data["results"]:
                games = data["results"]

                # If multiple games, show selection dialog
                if len(games) > 1:
                    selected_game = game_selection_dialog(games)
                    if not selected_game:
                        return None  # User canceled selection
                    game = selected_game
                else:
                    game = games[0]

                # Get platforms and genres
                platforms = ", ".join([p['platform']['name'] for p in game.get('platforms', []) if 'platform' in p][:3])
                genres = ", ".join([g['name'] for g in game.get('genres', [])][:3])

                return {
                    "name": game["name"],
                    "release_date": game.get("released", "N/A"),
                    "rating": game.get("rating", 0.0),
                    "image_url": game.get("background_image", ""),
                    "platform": platforms,
                    "genre": genres
                }
            else:
                messagebox.showinfo("API Result", "No games found with that name.")
        else:
            messagebox.showerror("API Error", f"Error {response.status_code}: Could not connect to game database")
    except Exception as e:
        messagebox.showerror("Connection Error", f"Failed to connect to game database: {e}")

    return None


# Game selection dialog for multiple search results
def game_selection_dialog(games):
    dialog = tk.Toplevel()
    dialog.title("Select Game")
    dialog.geometry("500x400")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="Multiple games found. Please select the correct one:", pady=10).pack()

    frame = tk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create scrollable listbox
    game_listbox = tk.Listbox(frame, width=70, height=15)
    scrollbar = tk.Scrollbar(frame, orient="vertical", command=game_listbox.yview)
    game_listbox.configure(yscrollcommand=scrollbar.set)

    game_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Add games to the listbox
    for i, game in enumerate(games):
        platforms = ", ".join([p['platform']['name'] for p in game.get('platforms', []) if 'platform' in p][:3])
        release_date = game.get("released", "N/A")
        display_text = f"{game['name']} ({release_date}) - {platforms}"
        game_listbox.insert(tk.END, display_text)

    selected_game = [None]  # Use list to store reference to selected game

    def on_select():
        selection = game_listbox.curselection()
        if selection:
            selected_game[0] = games[selection[0]]
            dialog.destroy()

    def on_cancel():
        dialog.destroy()

    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=10)

    tk.Button(button_frame, text="Select", command=on_select, bg="#1abc9c", width=10).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Cancel", command=on_cancel, bg="#e74c3c", width=10).pack(side=tk.LEFT, padx=5)

    dialog.wait_window()
    return selected_game[0]


# Add a game to the database
def add_game():
    game_name = entry_name.get()
    status = status_var.get()

    if not game_name:
        messagebox.showwarning("Input Error", "Enter a game name!")
        return

    # Show loading indicator
    status_label.config(text="Searching for game details...")
    root.update()

    # Fetch game details in a separate thread
    def fetch_and_add():
        game_data = fetch_game_details(game_name)

        if game_data:
            # Get current date in YYYY-MM-DD format
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")

            conn = sqlite3.connect("games.db")
            cursor = conn.cursor()

            # Check if game already exists
            cursor.execute("SELECT id FROM games WHERE name = ?", (game_data["name"],))
            existing = cursor.fetchone()

            if existing:
                # Update existing game
                cursor.execute("""UPDATE games SET 
                                status = ?, 
                                release_date = ?, 
                                rating = ?, 
                                image_url = ?,
                                platform = ?,
                                genre = ?,
                                date_modified = ?
                                WHERE name = ?""",
                               (status, game_data["release_date"], game_data["rating"],
                                game_data["image_url"], game_data["platform"], game_data["genre"],
                                current_date, game_data["name"]))
                messagebox.showinfo("Success", f"{game_data['name']} updated in your backlog!")
            else:
                # Insert new game
                cursor.execute("""INSERT INTO games 
                               (name, status, release_date, rating, image_url, platform, genre, date_added, date_modified) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                               (game_data["name"], status, game_data["release_date"],
                                game_data["rating"], game_data["image_url"], game_data["platform"],
                                game_data["genre"], current_date, current_date))

                # Get the ID of the newly inserted game
                game_id = cursor.lastrowid

                # Save image locally in the background
                if game_data["image_url"]:
                    threading.Thread(target=lambda: save_image_locally(game_data["image_url"], game_id)).start()

                messagebox.showinfo("Success", f"{game_data['name']} added to your backlog!")

            conn.commit()
            conn.close()

            # Reset UI elements
            entry_name.delete(0, tk.END)

            # Update the list with the new/updated game
            update_list()

        # Reset status label
        status_label.config(text="")

    # Run in a separate thread to keep UI responsive
    threading.Thread(target=fetch_and_add).start()


# Update the listbox with games from database
def update_list(listbox):
    # Clear existing items
    listbox.delete(0, tk.END)  # This is how you clear a Listbox

    # Connect to database and fetch games
    conn = sqlite3.connect("games.db")

    for item in listbox.get_children():
        listbox.delete(item)

    # Connect to database and fetch games
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()

    # Get filter values
    status_filter = filter_status_var.get()
    sort_by = sort_var.get()

    # Build query based on filters
    query = "SELECT id, name, status, release_date, rating, platform, genre FROM games"
    params = []

    if status_filter != "All":
        query += " WHERE status = ?"
        params.append(status_filter)

    # Add sorting
    if sort_by == "Name (A-Z)":
        query += " ORDER BY name ASC"
    elif sort_by == "Name (Z-A)":
        query += " ORDER BY name DESC"
    elif sort_by == "Rating (High-Low)":
        query += " ORDER BY rating DESC"
    elif sort_by == "Release Date (New-Old)":
        query += " ORDER BY release_date DESC"
    elif sort_by == "Release Date (Old-New)":
        query += " ORDER BY release_date ASC"
    elif sort_by == "Recently Added":
        query += " ORDER BY date_added DESC"

    cursor.execute(query, params)

    # Insert games into listbox
    for row in cursor.fetchall():
        game_id, name, status, release_date, rating, platform, genre = row

        # Format release date
        if release_date and release_date != "N/A":
            try:
                date_obj = datetime.datetime.strptime(release_date, "%Y-%m-%d")
                release_date = date_obj.strftime("%b %d, %Y")
            except:
                pass

        # Format rating
        if rating:
            rating = f"{rating:.1f}/5.0"
        else:
            rating = "N/A"

        listbox.insert("", tk.END, iid=str(game_id), values=(name, status, release_date, rating, platform))

    conn.close()

    # Update status bar
    update_status_bar()


# Status bar updates
def update_status_bar():
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()

    # Count games by status
    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Backlog'")
    backlog_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Playing'")
    playing_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Completed'")
    completed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games")
    total_count = cursor.fetchone()[0]

    conn.close()

    status_text = f"Total: {total_count} | Backlog: {backlog_count} | Playing: {playing_count} | Completed: {completed_count}"
    status_bar.config(text=status_text)


# Show game details when selected
def show_game_details(event):
    selected = listbox.selection()
    if selected:
        game_id = selected[0]

        conn = sqlite3.connect("games.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            # Extract data
            id, name, status, release_date, rating, image_url, platform, genre, playtime, notes, date_added, date_modified = result

            # Format dates
            if release_date and release_date != "N/A":
                try:
                    date_obj = datetime.datetime.strptime(release_date, "%Y-%m-%d")
                    release_date = date_obj.strftime("%B %d, %Y")
                except:
                    pass

            # Update details display
            details_text = f"Game: {name}\n"
            details_text += f"Status: {status}\n"
            details_text += f"Release Date: {release_date}\n"
            details_text += f"Rating: {rating}/5.0\n"
            details_text += f"Platform: {platform}\n"
            details_text += f"Genre: {genre}\n"
            details_text += f"Playtime: {playtime} hours\n"

            if notes:
                details_text += f"\nNotes: {notes}"

            game_details_label.config(text=details_text)

            # Show edit button
            edit_button.pack(side=tk.RIGHT, padx=5)

            # Handle image
            if image_url:
                img = get_cached_image(image_url)
                if img:
                    game_image_label.config(image=img)
                    game_image_label.image = img  # Keep a reference
                else:
                    game_image_label.config(image='', text="Loading image...")

                    # Try to load the image in a separate thread
                    def load_image_thread():
                        img = get_cached_image(image_url)
                        if img:
                            game_image_label.config(image=img, text="")
                            game_image_label.image = img
                        else:
                            game_image_label.config(text="Image not available")

                    threading.Thread(target=load_image_thread).start()
            else:
                game_image_label.config(image='', text="No image available")

        # Enable add playtime button
        add_playtime_button.config(state=tk.NORMAL)
    else:
        # Clear details if no game is selected
        game_details_label.config(text="")
        game_image_label.config(image='', text="")
        add_playtime_button.config(state=tk.DISABLED)
        edit_button.pack_forget()


# Delete selected game
def delete_game():
    selected = listbox.selection()
    if selected:
        game_id = selected[0]

        # Get game name for confirmation message
        conn = sqlite3.connect("games.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM games WHERE id = ?", (game_id,))
        game_name = cursor.fetchone()[0]
        conn.close()

        if messagebox.askyesno("Confirm", f"Delete '{game_name}' from your backlog?"):
            conn = sqlite3.connect("games.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
            conn.commit()
            conn.close()

            # Delete local image if exists
            image_path = f"game_images/{game_id}.jpg"
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except:
                    pass

            update_list()

            # Clear image and details when item is deleted
            game_image_label.config(image='', text="")
            game_details_label.config(text="")
            edit_button.pack_forget()


# Change game status
def change_status(new_status):
    selected = listbox.selection()
    if selected:
        game_id = selected[0]

        conn = sqlite3.connect("games.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE games SET status = ?, date_modified = ? WHERE id = ?",
                       (new_status, datetime.datetime.now().strftime("%Y-%m-%d"), game_id))
        conn.commit()
        conn.close()

        update_list()

        # Re-select the game to update the details panel
        listbox.selection_set(game_id)
        show_game_details(None)


# Log playtime for a game
def add_playtime():
    selected = listbox.selection()
    if selected:
        game_id = selected[0]

        # Get current playtime
        conn = sqlite3.connect("games.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, playtime FROM games WHERE id = ?", (game_id,))
        game_name, current_playtime = cursor.fetchone()
        conn.close()

        # Create dialog for entering playtime
        dialog = tk.Toplevel(root)
        dialog.title(f"Add Playtime - {game_name}")
        dialog.geometry("300x150")
        dialog.transient(root)
        dialog.grab_set()

        tk.Label(dialog, text=f"Current playtime: {current_playtime} hours").pack(pady=(10, 5))
        tk.Label(dialog, text="Add hours:").pack()

        hours_entry = tk.Entry(dialog, width=10)
        hours_entry.pack(pady=5)
        hours_entry.insert(0, "1")

        def submit_playtime():
            try:
                hours = float(hours_entry.get())
                if hours <= 0:
                    messagebox.showwarning("Invalid Input", "Please enter a positive number.")
                    return

                new_playtime = current_playtime + hours

                conn = sqlite3.connect("games.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE games SET playtime = ?, date_modified = ? WHERE id = ?",
                               (new_playtime, datetime.datetime.now().strftime("%Y-%m-%d"), game_id))
                conn.commit()
                conn.close()

                dialog.destroy()

                # Update the details display
                show_game_details(None)

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid number.")

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Add", command=submit_playtime, bg="#1abc9c").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy, bg="#e74c3c").pack(side=tk.LEFT, padx=5)


# Game details editing dialog
def edit_game_details():
    selected = listbox.selection()
    if not selected:
        return

    game_id = selected[0]

    # Fetch current game data
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
    game_data = cursor.fetchone()
    conn.close()

    if not game_data:
        return

    id, name, status, release_date, rating, image_url, platform, genre, playtime, notes, date_added, date_modified = game_data

    # Create edit dialog
    dialog = tk.Toplevel(root)
    dialog.title(f"Edit Game - {name}")
    dialog.geometry("400x500")
    dialog.transient(root)
    dialog.grab_set()

    # Create form fields
    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    # Name
    tk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
    name_entry = tk.Entry(frame, width=30)
    name_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
    name_entry.insert(0, name)

    # Status
    tk.Label(frame, text="Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
    status_combo = ttk.Combobox(frame, values=["Backlog", "Playing", "Completed"], width=27)
    status_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
    status_combo.set(status)

    # Platform
    tk.Label(frame, text="Platform:").grid(row=2, column=0, sticky=tk.W, pady=5)
    platform_entry = tk.Entry(frame, width=30)
    platform_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
    platform_entry.insert(0, platform if platform else "")

    # Genre
    tk.Label(frame, text="Genre:").grid(row=3, column=0, sticky=tk.W, pady=5)
    genre_entry = tk.Entry(frame, width=30)
    genre_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
    genre_entry.insert(0, genre if genre else "")

    # Release Date
    tk.Label(frame, text="Release Date:").grid(row=4, column=0, sticky=tk.W, pady=5)
    release_entry = tk.Entry(frame, width=30)
    release_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
    release_entry.insert(0, release_date if release_date else "")

    # Rating
    tk.Label(frame, text="Rating (0-5):").grid(row=5, column=0, sticky=tk.W, pady=5)
    rating_entry = tk.Entry(frame, width=30)
    rating_entry.grid(row=5, column=1, sticky=tk.W, pady=5)
    rating_entry.insert(0, str(rating) if rating else "0.0")

    # Playtime
    tk.Label(frame, text="Playtime (hours):").grid(row=6, column=0, sticky=tk.W, pady=5)
    playtime_entry = tk.Entry(frame, width=30)
    playtime_entry.grid(row=6, column=1, sticky=tk.W, pady=5)
    playtime_entry.insert(0, str(playtime) if playtime else "0")

    # Notes
    tk.Label(frame, text="Notes:").grid(row=7, column=0, sticky=tk.NW, pady=5)
    notes_text = tk.Text(frame, width=30, height=5)
    notes_text.grid(row=7, column=1, sticky=tk.W, pady=5)
    if notes:
        notes_text.insert("1.0", notes)

    # Image URL
    tk.Label(frame, text="Image URL:").grid(row=8, column=0, sticky=tk.W, pady=5)
    image_entry = tk.Entry(frame, width=30)
    image_entry.grid(row=8, column=1, sticky=tk.W, pady=5)
    image_entry.insert(0, image_url if image_url else "")

    def update_game():
        try:
            # Validate numeric fields
            try:
                new_rating = float(rating_entry.get())
                if not (0 <= new_rating <= 5):
                    messagebox.showwarning("Invalid Input", "Rating must be between 0 and 5.")
                    return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Rating must be a number.")
                return

            try:
                new_playtime = float(playtime_entry.get())
                if new_playtime < 0:
                    messagebox.showwarning("Invalid Input", "Playtime cannot be negative.")
                    return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Playtime must be a number.")
                return

            # Get values from form
            new_name = name_entry.get()
            new_status = status_combo.get()
            new_platform = platform_entry.get()
            new_genre = genre_entry.get()
            new_release_date = release_entry.get()
            new_notes = notes_text.get("1.0", tk.END).strip()
            new_image_url = image_entry.get()

            # Update database
            conn = sqlite3.connect("games.db")
            cursor = conn.cursor()
            cursor.execute("""UPDATE games SET 
                           name = ?, status = ?, release_date = ?, rating = ?, 
                           image_url = ?, platform = ?, genre = ?, playtime = ?, 
                           notes = ?, date_modified = ? 
                           WHERE id = ?""",
                           (new_name, new_status, new_release_date, new_rating,
                            new_image_url, new_platform, new_genre, new_playtime,
                            new_notes, datetime.datetime.now().strftime("%Y-%m-%d"), game_id))
            conn.commit()
            conn.close()

            dialog.destroy()
            update_list()

            # Re-select the game to update the details panel
            listbox.selection_set(game_id)
            show_game_details(None)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    # Buttons
    button_frame = tk.Frame(frame)
    button_frame.grid(row=9, column=0, columnspan=2, pady=10)

    tk.Button(button_frame, text="Save", command=update_game, bg="#1abc9c", width=10).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Cancel", command=dialog.destroy, bg="#e74c3c", width=10).pack(side=tk.LEFT, padx=5)


# Search functionality
def search_games():
    search_term = search_entry.get().lower()

    if not search_term:
        update_list()  # If search is cleared, show all games
        return

    # Clear existing items
    for item in listbox.get_children():
        listbox.delete(item)

    # Connect to database and search
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()

    # Search in multiple columns
    cursor.execute("""SELECT id, name, status, release_date, rating, platform, genre FROM games 
                   WHERE LOWER(name) LIKE ? OR LOWER(platform) LIKE ? OR LOWER(genre) LIKE ?""",
                   (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))

    # Insert matching games into listbox
    for row in cursor.fetchall():
        game_id, name, status, release_date, rating, platform, genre = row

        # Format release date
        if release_date and release_date != "N/A":
            try:
                date_obj = datetime.datetime.strptime(release_date, "%Y-%m-%d")
                release_date = date_obj.strftime("%b %d, %Y")
            except:
                pass

        # Format rating
        if rating:
            rating = f"{rating:.1f}/5.0"
        else:
            rating = "N/A"

        listbox.insert("", tk.END, iid=str(game_id), values=(name, status, release_date, rating, platform))

    conn.close()


# Export functionality
def export_games():
    # Ask for file location
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        title="Export Game List"
    )

    if not file_path:
        return  # User canceled

    try:
        # Connect to database
        conn = sqlite3.connect("games.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games")
        rows = cursor.fetchall()

        # Get column names
        cursor.execute("PRAGMA table_info(games)")
        columns = [info[1] for info in cursor.fetchall()]

        conn.close()

        # Write to CSV
        with open(file_path, 'w', newline='') as csvfile:
            import csv
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(columns)

            # Write data
            for row in rows:
                writer.writerow(row)

        messagebox.showinfo("Export Successful", f"Exported {len(rows)} games to {file_path}")

    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export games: {e}")


# Import functionality
def import_games():
    # Ask for file location
    file_path = filedialog.askopenfilename(
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        title="Import Game List"
    )

    if not file_path:
        return  # User canceled

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file)

            # Get header row
            try:
                header = next(reader)
            except StopIteration:
                messagebox.showerror("Import Error", "CSV file is empty")
                return

            # Convert header to lowercase for case-insensitive matching
            header = [col.lower() for col in header]

            # Get column indices
            column_indices = {}
            for i, column in enumerate(header):
                column_indices[column] = i

            # Check required columns
            required_columns = ["name", "status"]
            for column in required_columns:
                if column not in column_indices:
                    messagebox.showerror("Import Error", f"Required column '{column}' not found in CSV file")
                    return

            # Optional columns
            optional_columns = ["release_date", "rating", "image_url", "platform", "genre", "playtime", "notes"]

            # Connect to database
            conn = sqlite3.connect("games.db")
            cursor = conn.cursor()

            # Import each row
            imported = 0
            skipped = 0
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")

            try:
                for row in reader:
                    # Skip if row is too short
                    if len(row) < len(required_columns):
                        skipped += 1
                        continue

                    # Get required values
                    name = row[column_indices["name"]]
                    status = row[column_indices["status"]]

                    # Skip if name is empty
                    if not name:
                        skipped += 1
                        continue

                    # Check if game already exists
                    cursor.execute("SELECT id FROM games WHERE name = ?", (name,))
                    existing = cursor.fetchone()
                    if existing:
                        # Skip existing games
                        skipped += 1
                        continue

                    # Get optional values with defaults
                    release_date = row[column_indices["release_date"]] if "release_date" in column_indices and len(
                        row) > column_indices["release_date"] else "N/A"
                    rating = row[column_indices["rating"]] if "rating" in column_indices and len(row) > column_indices[
                        "rating"] else 0.0
                    image_url = row[column_indices["image_url"]] if "image_url" in column_indices and len(row) > \
                                                                    column_indices["image_url"] else ""
                    platform = row[column_indices["platform"]] if "platform" in column_indices and len(row) > \
                                                                  column_indices["platform"] else ""
                    genre = row[column_indices["genre"]] if "genre" in column_indices and len(row) > column_indices[
                        "genre"] else ""
                    playtime = row[column_indices["playtime"]] if "playtime" in column_indices and len(row) > \
                                                                  column_indices["playtime"] else 0
                    notes = row[column_indices["notes"]] if "notes" in column_indices and len(row) > column_indices[
                        "notes"] else ""

                    # Convert rating to float
                    try:
                        rating = float(rating)
                    except:
                        rating = 0.0

                    # Convert playtime to float
                    try:
                        playtime = float(playtime)
                    except:
                        playtime = 0.0

                    # Insert into database
                    cursor.execute("""INSERT INTO games 
                                      (name, status, release_date, rating, image_url, platform, genre, playtime, notes, date_added, date_modified) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                   (name, status, release_date, rating, image_url, platform, genre, playtime, notes,
                                    current_date, current_date))
                    imported += 1

                conn.commit()
                update_list()
                messagebox.showinfo("Import Successful",
                                    f"Imported {imported} games. Skipped {skipped} games (duplicates or invalid).")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import games: {e}")
            finally:
                conn.close()
    except Exception as e:
        messagebox.showerror("Import Error", f"Failed to open CSV file: {e}")
    # Get required values
    name = row[column_indices["name"]]
    status = row[column_indices["status"]]

    # Skip if name is empty
    if not name:
        skipped += 1
        # continue

    # Check if game already exists
    cursor.execute("SELECT id FROM games WHERE name = ?", (name,))
    existing = cursor.fetchone()

    if existing:
        # Skip existing games
        skipped += 1
        # continue

    # Get optional values with defaults
    release_date = row[column_indices["release_date"]] if "release_date" in column_indices and len(row) > \
                                                          column_indices["release_date"] else "N/A"
    rating = row[column_indices["rating"]] if "rating" in column_indices and len(row) > column_indices[
        "rating"] else 0.0
    image_url = row[column_indices["image_url"]] if "image_url" in column_indices and len(row) > column_indices[
        "image_url"] else ""
    platform = row[column_indices["platform"]] if "platform" in column_indices and len(row) > column_indices[
        "platform"] else ""
    genre = row[column_indices["genre"]] if "genre" in column_indices and len(row) > column_indices["genre"] else ""
    playtime = row[column_indices["playtime"]] if "playtime" in column_indices and len(row) > column_indices[
        "playtime"] else 0
    notes = row[column_indices["notes"]] if "notes" in column_indices and len(row) > column_indices["notes"] else ""

    # Convert rating to float
    try:
        rating = float(rating)
    except:
        rating = 0.0

    # Convert playtime to float
    try:
        playtime = float(playtime)
    except:
        playtime = 0.0

    # Insert into database
    cursor.execute("""INSERT INTO games 
                                   (name, status, release_date, rating, image_url, platform, genre, playtime, notes, date_added, date_modified) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (name, status, release_date, rating, image_url, platform, genre, playtime, notes, current_date,
                    current_date))

    imported += 1
    conn.commit()
    conn.close()


# Update the list
update_list(listbox=Treeview)

try:
    messagebox.showinfo("Import Successful", f"Imported {imported} games. Skipped {skipped} games (duplicates or invalid).")
except Exception as e:
    messagebox.showerror("Import Error", f"Failed to import games: {e}")

# Generate statistics
def show_statistics():
    # Connect to database
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()

    # Get statistics
    cursor.execute("SELECT COUNT(*) FROM games")
    total_games = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Backlog'")
    backlog_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Playing'")
    playing_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Completed'")
    completed_count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(playtime) FROM games")
    total_playtime = cursor.fetchone()[0] or 0

    cursor.execute("SELECT AVG(rating) FROM games WHERE rating > 0")
    avg_rating = cursor.fetchone()[0] or 0

    cursor.execute("SELECT name, rating FROM games WHERE rating = (SELECT MAX(rating) FROM games) LIMIT 1")
    top_rated = cursor.fetchone()
    top_rated_game = top_rated[0] if top_rated else "None"
    top_rating = top_rated[1] if top_rated else 0

    cursor.execute("SELECT name, playtime FROM games WHERE playtime = (SELECT MAX(playtime) FROM games) LIMIT 1")
    most_played = cursor.fetchone()
    most_played_game = most_played[0] if most_played else "None"
    most_played_time = most_played[1] if most_played else 0

    cursor.execute("SELECT genre, COUNT(*) FROM games WHERE genre != '' GROUP BY genre ORDER BY COUNT(*) DESC LIMIT 1")
    top_genre = cursor.fetchone()
    top_genre_name = top_genre[0] if top_genre else "None"
    top_genre_count = top_genre[1] if top_genre else 0

    cursor.execute(
        "SELECT platform, COUNT(*) FROM games WHERE platform != '' GROUP BY platform ORDER BY COUNT(*) DESC LIMIT 1")
    top_platform = cursor.fetchone()
    top_platform_name = top_platform[0] if top_platform else "None"
    top_platform_count = top_platform[1] if top_platform else 0

    cursor.execute(
        "SELECT SUBSTR(release_date, 1, 4) as year, COUNT(*) FROM games WHERE release_date != 'N/A' GROUP BY year ORDER BY COUNT(*) DESC LIMIT 1")
    top_year = cursor.fetchone()
    top_year_value = top_year[0] if top_year else "None"
    top_year_count = top_year[1] if top_year else 0

    conn.close()

    # Create statistics window
    stats_window = tk.Toplevel(root)
    stats_window.title("Backlog Statistics")
    stats_window.geometry("400x500")
    stats_window.transient(root)

    # Main frame
    main_frame = tk.Frame(stats_window, padx=15, pady=15, bg="#34495e")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    title_label = tk.Label(main_frame, text="Your Gaming Statistics", font=("Arial", 16, "bold"), fg="white",
                           bg="#34495e")
    title_label.pack(pady=(0, 15))

    # Collection statistics
    collection_frame = tk.LabelFrame(main_frame, text="Collection", padx=10, pady=10, fg="white", bg="#2c3e50")
    collection_frame.pack(fill=tk.X, pady=5)

    tk.Label(collection_frame, text=f"Total Games: {total_games}", fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)
    tk.Label(collection_frame,
             text=f"Games in Backlog: {backlog_count} ({backlog_count / total_games * 100:.1f}% of total)" if total_games > 0 else "Games in Backlog: 0 (0.0% of total)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)
    tk.Label(collection_frame,
             text=f"Games Playing: {playing_count} ({playing_count / total_games * 100:.1f}% of total)" if total_games > 0 else "Games Playing: 0 (0.0% of total)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)
    tk.Label(collection_frame,
             text=f"Games Completed: {completed_count} ({completed_count / total_games * 100:.1f}% of total)" if total_games > 0 else "Games Completed: 0 (0.0% of total)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)

    # Playtime statistics
    playtime_frame = tk.LabelFrame(main_frame, text="Playtime", padx=10, pady=10, fg="white", bg="#2c3e50")
    playtime_frame.pack(fill=tk.X, pady=5)

    tk.Label(playtime_frame, text=f"Total Hours Played: {total_playtime:.1f}", fg="white", bg="#2c3e50",
             anchor="w").pack(fill=tk.X)
    tk.Label(playtime_frame,
             text=f"Average Hours per Game: {total_playtime / total_games:.1f}" if total_games > 0 else "Average Hours per Game: 0.0",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)
    tk.Label(playtime_frame, text=f"Most Played Game: {most_played_game} ({most_played_time:.1f} hours)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)

    # Ratings statistics
    ratings_frame = tk.LabelFrame(main_frame, text="Ratings", padx=10, pady=10, fg="white", bg="#2c3e50")
    ratings_frame.pack(fill=tk.X, pady=5)

    tk.Label(ratings_frame, text=f"Average Rating: {avg_rating:.1f}/5.0", fg="white", bg="#2c3e50", anchor="w").pack(
        fill=tk.X)
    tk.Label(ratings_frame, text=f"Highest Rated Game: {top_rated_game} ({top_rating}/5.0)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)

    # Trends
    trends_frame = tk.LabelFrame(main_frame, text="Trends", padx=10, pady=10, fg="white", bg="#2c3e50")
    trends_frame.pack(fill=tk.X, pady=5)

    tk.Label(trends_frame, text=f"Most Common Genre: {top_genre_name} ({top_genre_count} games)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)
    tk.Label(trends_frame, text=f"Most Common Platform: {top_platform_name} ({top_platform_count} games)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)
    tk.Label(trends_frame, text=f"Most Common Release Year: {top_year_value} ({top_year_count} games)",
             fg="white", bg="#2c3e50", anchor="w").pack(fill=tk.X)

    # Close button
    tk.Button(main_frame, text="Close", command=stats_window.destroy, bg="#e74c3c", fg="white", width=15).pack(pady=15)


# Progress calculation
def calculate_completion_rate():
    conn = sqlite3.connect("games.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM games")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM games WHERE status='Completed'")
    completed = cursor.fetchone()[0]

    conn.close()

    if total > 0:
        return completed / total * 100
    return 0


# Create a progress bar
def update_progress():
    completion_rate = calculate_completion_rate()
    progress_bar["value"] = completion_rate
    progress_label.config(text=f"Completion Rate: {completion_rate:.1f}%")


# GUI Setup
root = tk.Tk()
root.title("Advanced Gaming Backlog Tracker")
root.geometry("950x650")
root.configure(bg="#2c3e50")

# Create a menu bar
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# File menu
file_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Export Games", command=export_games)
file_menu.add_command(label="Import Games", command=import_games)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# View menu
view_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="View", menu=view_menu)
view_menu.add_command(label="Statistics", command=show_statistics)
view_menu.add_command(label="Refresh", command=update_list)

# Main container
main_container = tk.Frame(root, bg="#34495e")
main_container.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Left side - Game entry and filters
left_frame = tk.Frame(main_container, bg="#34495e", width=300)
left_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

# Game entry section
entry_frame = tk.LabelFrame(left_frame, text="Add Game", padx=10, pady=10, fg="white", bg="#34495e")
entry_frame.pack(fill=tk.X, pady=(0, 10))

tk.Label(entry_frame, text="Game Name:", fg="white", bg="#34495e").grid(row=0, column=0, sticky=tk.W, pady=5)
entry_name = tk.Entry(entry_frame, width=25)
entry_name.grid(row=0, column=1, pady=5)

tk.Label(entry_frame, text="Status:", fg="white", bg="#34495e").grid(row=1, column=0, sticky=tk.W, pady=5)
status_var = tk.StringVar()
status_var.set("Backlog")
status_menu = ttk.Combobox(entry_frame, textvariable=status_var, values=["Backlog", "Playing", "Completed"], width=22)
status_menu.grid(row=1, column=1, pady=5)

add_button = tk.Button(entry_frame, text="Add Game", command=add_game, bg="#1abc9c", fg="white")
add_button.grid(row=2, column=0, columnspan=2, pady=10, sticky=tk.EW)

# Status indicator
status_label = tk.Label(entry_frame, text="", fg="white", bg="#34495e")
status_label.grid(row=3, column=0, columnspan=2, pady=5, sticky=tk.W)

# Filters section
filter_frame = tk.LabelFrame(left_frame, text="Filters", padx=10, pady=10, fg="white", bg="#34495e")
filter_frame.pack(fill=tk.X, pady=10)

tk.Label(filter_frame, text="Status:", fg="white", bg="#34495e").grid(row=0, column=0, sticky=tk.W, pady=5)
filter_status_var = tk.StringVar()
filter_status_var.set("All")
filter_status_menu = ttk.Combobox(filter_frame, textvariable=filter_status_var,
                                  values=["All", "Backlog", "Playing", "Completed"], width=22)
filter_status_menu.grid(row=0, column=1, pady=5)

tk.Label(filter_frame, text="Sort By:", fg="white", bg="#34495e").grid(row=1, column=0, sticky=tk.W, pady=5)
sort_var = tk.StringVar()
sort_var.set("Name (A-Z)")
sort_menu = ttk.Combobox(filter_frame, textvariable=sort_var,
                         values=["Name (A-Z)", "Name (Z-A)", "Rating (High-Low)",
                                 "Release Date (New-Old)", "Release Date (Old-New)", "Recently Added"], width=22)
sort_menu.grid(row=1, column=1, pady=5)

apply_button = tk.Button(filter_frame, text="Apply Filters", command=update_list, bg="#3498db", fg="white")
apply_button.grid(row=2, column=0, columnspan=2, pady=10, sticky=tk.EW)

# Search section
search_frame = tk.LabelFrame(left_frame, text="Search", padx=10, pady=10, fg="white", bg="#34495e")
search_frame.pack(fill=tk.X, pady=10)

search_entry = tk.Entry(search_frame, width=25)
search_entry.pack(fill=tk.X, pady=5)

search_button = tk.Button(search_frame, text="Search", command=search_games, bg="#9b59b6", fg="white")
search_button.pack(fill=tk.X, pady=5)

# Progress section
progress_frame = tk.LabelFrame(left_frame, text="Progress", padx=10, pady=10, fg="white", bg="#34495e")
progress_frame.pack(fill=tk.X, pady=10)

progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
progress_bar.pack(fill=tk.X, pady=5)

progress_label = tk.Label(progress_frame, text="Completion Rate: 0.0%", fg="white", bg="#34495e")
progress_label.pack(pady=5)

# Right side - Game list and details
right_frame = tk.Frame(main_container, bg="#34495e")
right_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

# Game list
list_frame = tk.Frame(right_frame, bg="#34495e")
list_frame.pack(fill=tk.BOTH, expand=True)

# Create Treeview with scrollbar
tree_frame = tk.Frame(list_frame)
tree_frame.pack(fill=tk.BOTH, expand=True)

tree_scroll = tk.Scrollbar(tree_frame)
tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

listbox: Treeview = ttk.Treeview(tree_frame, columns=("Name", "Status", "Release Date", "Rating", "Platform"), show="headings",
                       yscrollcommand=tree_scroll.set)
listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

tree_scroll.config(command=listbox.yview)

# Define column widths
listbox.column("Name", width=150)
listbox.column("Status", width=80)
listbox.column("Release Date", width=100)
listbox.column("Rating", width=80)
listbox.column("Platform", width=120)

# Add column headings
listbox.heading("Name", text="Game Name")
listbox.heading("Status", text="Status")
listbox.heading("Release Date", text="Release Date")
listbox.heading("Rating", text="Rating")
listbox.heading("Platform", text="Platform")

# Bind selection event
listbox.bind("<<TreeviewSelect>>", show_game_details)

# Button frame
button_frame = tk.Frame(list_frame, bg="#34495e")
button_frame.pack(fill=tk.X, pady=5)

# Action buttons
delete_button = tk.Button(button_frame, text="Delete", command=delete_game, bg="#e74c3c", fg="white")
delete_button.pack(side=tk.LEFT, padx=5)

backlog_button = tk.Button(button_frame, text="Set as Backlog", command=lambda: change_status("Backlog"), bg="#f39c12",
                           fg="white")
backlog_button.pack(side=tk.LEFT, padx=5)

playing_button = tk.Button(button_frame, text="Set as Playing", command=lambda: change_status("Playing"), bg="#2ecc71",
                           fg="white")
playing_button.pack(side=tk.LEFT, padx=5)

completed_button = tk.Button(button_frame, text="Set as Completed", command=lambda: change_status("Completed"),
                             bg="#3498db", fg="white")
completed_button.pack(side=tk.LEFT, padx=5)

add_playtime_button = tk.Button(button_frame, text="Log Playtime", command=add_playtime, bg="#9b59b6", fg="white",
                                state=tk.DISABLED)
add_playtime_button.pack(side=tk.LEFT, padx=5)

edit_button = tk.Button(button_frame, text="Edit Details", command=edit_game_details, bg="#16a085", fg="white")
# Don't pack the edit button yet - we'll show it only when a game is selected

# Game details section
details_frame = tk.Frame(right_frame, bg="#34495e", height=200)
details_frame.pack(fill=tk.X, pady=10)

# Game image on the left
game_image_label = tk.Label(details_frame, bg="#2c3e50", width=25, height=15)
game_image_label.pack(side=tk.LEFT, padx=10, pady=10)

# Game details on the right
game_details_label = tk.Label(details_frame, text="", fg="white", bg="#2c3e50", justify=tk.LEFT, anchor="nw", padx=10,
                              pady=10)
game_details_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

# Status bar
status_bar = tk.Label(root, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#2c3e50", fg="white")
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# Initialization
init_db()
update_list()
update_progress()

# Add bindings to automatically refresh when filters change
filter_status_menu.bind("<<ComboboxSelected>>", lambda e: update_list())
sort_menu.bind("<<ComboboxSelected>>", lambda e: update_list())
search_entry.bind("<Return>", lambda e: search_games())

# Set up keyboard shortcuts
root.bind("<Control-a>", lambda e: add_game())
root.bind("<Delete>", lambda e: delete_game())
root.bind("<Control-f>", lambda e: search_entry.focus_set())

# Configure style for ttk elements
style = ttk.Style()
style.configure("Treeview", background="#2c3e50", fieldbackground="#2c3e50", foreground="white")
style.configure("Treeview.Heading", background="#34495e", foreground="white", font=('Arial', 9, 'bold'))
style.map('Treeview', background=[('selected', '#3498db')])

# Start the main loop
root.mainloop()