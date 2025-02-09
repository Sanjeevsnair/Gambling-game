import time
import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import random
import pandas as pd

# Firebase Configuration
cred = credentials.Certificate("gambling-game-exodia-game-firebase-adminsdk-fbsvc-8f08c488a4.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://gambling-game-exodia-game-default-rtdb.firebaseio.com/"
    })
    

# Initialize Firebase references
timer_ref = db.reference("timers")

# Function to start the preparation timer
def start_preparation_timer():
    timer_ref.update({
        "is_preparation_timer_running": True,
        "is_placebet_timer_running": False
    })
    preparation_time = 20  # 1 minute
    while preparation_time > 0:
        timer_ref.update({"preparation_time_left": preparation_time})
        st.session_state.preparation_timer_placeholder.write(f"⏳ Preparation Time: {preparation_time} seconds")
        time.sleep(1)
        preparation_time -= 1
    timer_ref.update({
        "is_preparation_timer_running": False,
        "preparation_time_left": 0
    })
    st.session_state.preparation_timer_placeholder.write("Preparation Time Ended!")
    start_placebet_timer()
    st.session_state.placebet_timer_placeholder.write("Place Bet Time Ended!")

# Function to start the place bet timer
def start_placebet_timer():
    timer_ref.update({
        "is_placebet_timer_running": True
    })
    placebet_time = 20  # 1 minute
    while placebet_time > 0:
        timer_ref.update({"placebet_time_left": placebet_time})
        st.session_state.placebet_timer_placeholder.write(f"⏳ Place Bet Time: {placebet_time} seconds")
        time.sleep(1)
        placebet_time -= 1
    timer_ref.update({
        "is_placebet_timer_running": False,
        "placebet_time_left": 0
    })
    

st.title("🎲 Volunteer Game Management")

try:
    scores_ref = db.reference("scores")
    scores_data = scores_ref.get()
    
    # Convert the list to a dictionary if needed
    if isinstance(scores_data, list):
        scores = {str(i): score for i, score in enumerate(scores_data) if score is not None}
    else:
        scores = scores_data if isinstance(scores_data, dict) else {}
    
    # Create DataFrame
    scores_df = pd.DataFrame(list(scores.items()), columns=["Player", "Score"])
    
except Exception as e:
    st.error(f"Error fetching scores: {str(e)}")
    scores_df = pd.DataFrame(columns=["Player", "Score"])


def process_loan_settlement(winning_player_id):
    active_loans_ref = db.reference("active_loans")
    scores_ref = db.reference("scores")
    loans = active_loans_ref.get() or {}
    
    for loan_id, loan in loans.items():
        if loan['status'] == 'active':  # Only process active loans
            borrower_id = loan['borrower_id']
            lender_id = loan['lender_id']
            loan_amount = loan['amount']
            
            if borrower_id == winning_player_id:
                # Borrower wins: repay 50% of the loan
                payback_amount = int(loan_amount * 0.5)
                
                # Update borrower's score
                borrower_score = scores_ref.child(borrower_id).get() or 0
                scores_ref.child(borrower_id).set(borrower_score - payback_amount)
                
                # Update lender's score
                lender_score = scores_ref.child(lender_id).get() or 0
                scores_ref.child(lender_id).set(lender_score + payback_amount)
                
                # Mark loan as settled
                active_loans_ref.child(loan_id).update({
                    'status': 'settled',
                    'settlement_date': time.time()
                })
                
                st.success(f"✅ Loan settled: {loan['borrower_name']} repaid {payback_amount} points to {loan['lender_name']}.")
            
            else:
                # Borrower loses: repay loan amount + 10-point penalty
                penalty_amount = loan_amount + 10
                
                # Update borrower's score
                borrower_score = scores_ref.child(borrower_id).get() or 0
                scores_ref.child(borrower_id).set(borrower_score - penalty_amount)
                
                # Update lender's score
                lender_score = scores_ref.child(lender_id).get() or 0
                scores_ref.child(lender_id).set(lender_score + penalty_amount)
                
                # Mark loan as settled with penalty
                active_loans_ref.child(loan_id).update({
                    'status': 'settled_with_penalty',
                    'settlement_date': time.time()
                })
                
                st.success(f"✅ Loan settled with penalty: {loan['borrower_name']} repaid {penalty_amount} points to {loan['lender_name']}.")


def is_prime(n):
    """Check if a number is prime."""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True



# Display all current scores in a table
st.sidebar.subheader("📊 Current Scores")
st.sidebar.table(scores_df)

# Display Player Bets
# Display Player Bets
st.sidebar.header("🎯 Active Bets")
bets_ref = db.reference("bets").get()

choosed_numbers = []

if bets_ref:
    try:
        bet_data = []
        
        # Handle both list and dictionary data structures
        if isinstance(bets_ref, list):
            # Handle list structure
            for index, bet_info in enumerate(bets_ref):
                if bet_info and isinstance(bet_info, dict):  # Check if bet exists and is a dictionary
                    
                    bet_data.append({
                        "Player": bet_info.get("player_name", "Unknown"),
                        "Chosen Number": bet_info.get("chosen_number", "N/A"),
                        "Bet Amount": bet_info.get("bet_amount", 0)
                    })
        elif isinstance(bets_ref, dict):
            # Handle dictionary structure
            for bet_id, bet_info in bets_ref.items():
                if isinstance(bet_info, dict):
                    
                    bet_data.append({
                        "Player": bet_info.get("player_name", "Unknown"),
                        "Chosen Number": bet_info.get("chosen_number", "N/A"),
                        "Bet Amount": bet_info.get("bet_amount", 0)
                    })
        
        if bet_data:  # Only create and display DataFrame if we have data
            df = pd.DataFrame(bet_data)
            st.sidebar.table(df)
            data = [entry["Chosen Number"] for entry in bet_data]
            choosed_numbers = data
        else:
            st.sidebar.info("No active bets at the moment.")
            
    except Exception as e:
        st.sidebar.error(f"Error processing bets: {str(e)}")
        # Debug information
        st.sidebar.write("Data type:", type(bets_ref))
        st.sidebar.write("Raw bet data:", bets_ref)
else:
    st.sidebar.info("No active bets at the moment.")
    
# Edit player points
st.sidebar.subheader("✏️ Edit Player Points")
for idx, row in scores_df.iterrows():
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.sidebar.text(f"Player {row['Player']}")
    with col2:
        new_score = st.sidebar.number_input(
            f"Score for Player {row['Player']}", 
            value=int(row['Score']),
            key=f"score_{row['Player']}"
        )
    with col3:
        if st.sidebar.button("Update", key=f"update_{row['Player']}"):
            scores_ref.child(row['Player']).set(int(new_score))
            st.sidebar.success(f"Updated Player {row['Player']}'s score to {new_score}")

def penalize_non_betting_players():
    """Deduct points from players who didn't place bets."""
    scores_ref = db.reference("scores")
    bets_ref = db.reference("bets").get() or {}
    scores = scores_ref.get() or {}

    # Check if scores is a list or dictionary
    if isinstance(scores, list):
        # Convert list to dictionary if needed
        scores_dict = {str(i): score for i, score in enumerate(scores) if score is not None}
    elif isinstance(scores, dict):
        scores_dict = scores
    else:
        scores_dict = {}

    # Get list of players who placed bets
    if isinstance(bets_ref, list):
        # Convert list to dictionary if needed
        bets_dict = {str(i): bet for i, bet in enumerate(bets_ref) if isinstance(bet, dict)}
    elif isinstance(bets_ref, dict):
        bets_dict = bets_ref
    else:
        bets_dict = {}

    betting_players = set(bets_dict.keys())
    # Get all players
    all_players = set(scores_dict.keys())
    # Find players who didn't bet
    non_betting_players = all_players - betting_players

    penalties = []
    for player_id in non_betting_players:
        current_score = scores_dict.get(player_id, 0)
        new_score = max(0, current_score - 20)  # Ensure score doesn't go below 0
        scores_ref.child(player_id).set(new_score)
        penalties.append((player_id, current_score, new_score))

    return penalties

# ... (previous imports, Firebase setup, and helper functions remain the same)

# ... (previous imports, Firebase setup, and helper functions remain the same)

def get_highest_betters(bets_ref, winning_number):
    """
    Find players who bet the highest amount on the winning number.
    Returns a list of tuples (player_id, bet_amount) for highest betters.
    """
    highest_bet = 0
    highest_betters = []
    
    # First find all players who chose the winning number
    for player, bet in bets_ref.items():
        if bet["chosen_number"] == winning_number:
            bet_amount = bet["bet_amount"]
            if bet_amount > highest_bet:
                # New highest bet - clear previous and start new list
                highest_bet = bet_amount
                highest_betters = [(player, bet_amount)]
            elif bet_amount == highest_bet:
                # Same highest bet - add to list
                highest_betters.append((player, bet_amount))
    
    return highest_betters

# Initialize session state for timers
if 'preparation_timer_placeholder' not in st.session_state:
    st.session_state.preparation_timer_placeholder = st.empty()
if 'placebet_timer_placeholder' not in st.session_state:
    st.session_state.placebet_timer_placeholder = st.empty()

# Start Preparation Timer Button
if st.button("Start Preparation Timer (1 Minute)"):
    db.reference("winning_number").delete()
    start_preparation_timer()

# Announce Winning Number
if st.button("🎯 Announce Winning Number"):
    print(choosed_numbers)
    print()
    winning_number = random.choice(choosed_numbers)  # Random number between 1 and 10
    db.reference("winning_number").set(winning_number)
    st.success(f"🏆 Winning Number: {winning_number}")
    
    
    
    # Safely get bets
    bets_ref = db.reference("bets").get()
    total_players = len(db.reference("scores").get() or {})
    total_bets = len(bets_ref or {})
    
    # Check if any bets were placed
    if total_bets == 0:
        st.warning("❌ No players placed bets this round!")
        penalties = penalize_non_betting_players()
        for player_id, old_score, new_score in penalties:
            st.warning(f"Player {player_id} penalized: {old_score} → {new_score} (-20 points)")
    
    # If some players placed bets but not all
    elif total_bets < total_players:
        st.warning(f"Only {total_bets} out of {total_players} players placed bets!")
        penalties = penalize_non_betting_players()
        for player_id, old_score, new_score in penalties:
            st.warning(f"Player {player_id} penalized: {old_score} → {new_score} (-20 points)")
    
    # Safely get bets
    bets_ref = db.reference("bets").get()

    # Check if bets_ref is a list or dictionary
    if isinstance(bets_ref, list):
        # Convert list to dictionary if needed
        bets = {str(i): bet for i, bet in enumerate(bets_ref) if isinstance(bet, dict)}
    elif isinstance(bets_ref, dict):
        bets = bets_ref
    else:
        bets = {}

    # Calculate total pool
    total_pool = sum(bet.get("bet_amount", 0) for bet in bets.values())

    # Process bets if any exist
    if bets:
        highest_betters = get_highest_betters(bets, winning_number)
    
        if not highest_betters:
            st.info("No one chose the winning number!")
        elif len(highest_betters) > 1:
            # Multiple players with same highest bet - It's a draw
            bet_amount = highest_betters[0][1]  # Get the bet amount (all are same)
            players = [p[0] for p in highest_betters]
            st.warning(f"🤝 Draw! Multiple players bet {bet_amount} points on number {winning_number}")
            st.write("Players involved in draw:", ", ".join(players))
            st.warning("All players lose their bet points!")
        else:
            # Single winner
            winner, winning_bet = highest_betters[0]
            current_score = scores_ref.child(winner).get() or 100
            new_score = current_score + total_pool
        
            # Safely check for prime numbers
            try:
                winner_bet = bets.get(winner, {})
                if winner_bet and is_prime(winning_number) and is_prime(winner_bet.get("chosen_number", 0)):
                    new_score += 20  # Additional 20 points for choosing a prime number
                    st.success(f"🎉 Player {winner} gets an additional 20 points for choosing a prime number!")
            except Exception as e:
                st.warning(f"Could not process prime number bonus: {str(e)}")
        
            scores_ref.child(winner).set(new_score)
            st.success(f"🏆 Player {winner} wins with bet of {winning_bet} points on number {winning_number}!")
            st.success(f"Won {total_pool} points! New Score: {new_score}")
        
            # Process loan settlements
            process_loan_settlement(winner)
    
    # Show updated scores in a table
    st.subheader("📊 Updated Scores")
    updated_scores = scores_ref.get()

    # Check if updated_scores is a list or dictionary
    if isinstance(updated_scores, list):
        # Convert list to dictionary if needed
        scores_dict = {str(i): score for i, score in enumerate(updated_scores) if score is not None}
    elif isinstance(updated_scores, dict):
        scores_dict = updated_scores
    else:
        scores_dict = {}

    # Create DataFrame
    scores_df = pd.DataFrame(list(scores_dict.items()), columns=["Player", "Score"])

    # Display the DataFrame
    st.table(scores_df)
    
    # Clear bets for next round

    db.reference("bets").delete()
    st.warning("🔄 Bets cleared for the next round.")
    # Reset the bet_placed flag for all players
    st.session_state.bet_placed = False