import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime, timedelta
import pandas as pd

class InterestRateSwapCVA:
    """
    Calculate CVA for Interest Rate Swap using Monte Carlo simulation
    """
    
    def __init__(self, notional, fixed_rate, maturity_years, 
                 counterparty_spread, recovery_rate, num_simulations=1000):
        self.notional = notional
        self.fixed_rate = fixed_rate
        self.maturity_years = maturity_years
        self.counterparty_spread = counterparty_spread
        self.recovery_rate = recovery_rate
        self.num_simulations = num_simulations
        self.time_steps = int(maturity_years * 12)  # Monthly steps
        
    def simulate_interest_rates(self, initial_rate=0.03, volatility=0.01):
        """
        Simulate interest rate paths using Hull-White model
        """
        dt = 1/12  # Monthly time step
        rates = np.zeros((self.num_simulations, self.time_steps + 1))
        rates[:, 0] = initial_rate
        
        # Mean reversion parameters
        kappa = 0.1  # Mean reversion speed
        theta = 0.03  # Long-term mean
        
        for t in range(1, self.time_steps + 1):
            dW = np.random.normal(0, np.sqrt(dt), self.num_simulations)
            rates[:, t] = rates[:, t-1] + kappa * (theta - rates[:, t-1]) * dt + volatility * dW
            
        return rates
    
    def calculate_swap_values(self, rate_paths):
        """
        Calculate swap mark-to-market values for all paths and time steps
        """
        swap_values = np.zeros((self.num_simulations, self.time_steps + 1))
        dt = 1/12
        
        for t in range(self.time_steps + 1):
            remaining_time = self.maturity_years - t * dt
            if remaining_time <= 0:
                continue
                
            # Discount factors
            remaining_steps = self.time_steps - t
            for sim in range(self.num_simulations):
                # Calculate PV of fixed leg
                fixed_leg_pv = 0
                floating_leg_pv = 0
                
                for future_t in range(t + 1, self.time_steps + 1):
                    time_to_payment = (future_t - t) * dt
                    discount_factor = np.exp(-rate_paths[sim, t] * time_to_payment)
                    
                    # Fixed leg payment
                    fixed_leg_pv += self.notional * self.fixed_rate * dt * discount_factor
                    
                    # Floating leg payment (simplified)
                    forward_rate = rate_paths[sim, future_t-1]
                    floating_leg_pv += self.notional * forward_rate * dt * discount_factor
                
                # Swap value (receive fixed, pay floating)
                swap_values[sim, t] = fixed_leg_pv - floating_leg_pv
                
        return swap_values
    
    def calculate_exposure_profiles(self, swap_values):
        """
        Calculate Expected Positive Exposure (EPE) and Expected Negative Exposure (ENE)
        """
        positive_exposures = np.maximum(swap_values, 0)
        negative_exposures = np.minimum(swap_values, 0)
        
        epe = np.mean(positive_exposures, axis=0)
        ene = np.mean(negative_exposures, axis=0)
        
        # Also calculate percentiles
        epe_95 = np.percentile(positive_exposures, 95, axis=0)
        ene_5 = np.percentile(negative_exposures, 5, axis=0)
        
        return epe, ene, epe_95, ene_5
    
    def calculate_cva(self, epe, time_grid):
        """
        Calculate CVA using EPE profile and counterparty default probability
        """
        dt = 1/12
        survival_prob = np.exp(-self.counterparty_spread * time_grid)
        default_prob = -np.diff(survival_prob, prepend=1)
        
        # CVA = LGD * sum(EPE * PD * DF)
        lgd = 1 - self.recovery_rate
        discount_factors = np.exp(-0.03 * time_grid)  # Risk-free discount
        
        cva = lgd * np.sum(epe * default_prob * discount_factors)
        
        return cva
    
    def run_analysis(self):
        """
        Run the complete CVA analysis
        """
        # Simulate interest rates
        rate_paths = self.simulate_interest_rates()
        
        # Calculate swap values
        swap_values = self.calculate_swap_values(rate_paths)
        
        # Calculate exposure profiles
        epe, ene, epe_95, ene_5 = self.calculate_exposure_profiles(swap_values)
        
        # Time grid
        time_grid = np.linspace(0, self.maturity_years, self.time_steps + 1)
        
        # Calculate CVA
        cva = self.calculate_cva(epe, time_grid)
        
        return {
            'time_grid': time_grid,
            'epe': epe,
            'ene': ene,
            'epe_95': epe_95,
            'ene_5': ene_5,
            'cva': cva,
            'rate_paths': rate_paths,
            'swap_values': swap_values
        }

class CVACalculatorGUI:
    """
    Tkinter GUI for CVA Calculator
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("CVA Calculator - Interest Rate Swap")
        self.root.geometry("1200x800")
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Create main frames
        self.create_input_frame()
        self.create_results_frame()
        self.create_plot_frame()
        
        # Set default values
        self.set_default_values()
        
    def create_input_frame(self):
        """Create input parameter frame"""
        input_frame = ttk.LabelFrame(self.root, text="Swap Parameters", padding="10")
        input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Counterparty info
        ttk.Label(input_frame, text="Counterparty:").grid(row=0, column=0, sticky="w")
        self.counterparty_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.counterparty_var, width=20).grid(row=0, column=1, padx=5)
        
        # Swap parameters
        parameters = [
            ("Notional (millions):", "notional"),
            ("Fixed Rate (%):", "fixed_rate"),
            ("Maturity (years):", "maturity"),
            ("Counterparty Spread (bps):", "cp_spread"),
            ("Recovery Rate (%):", "recovery"),
            ("Simulations:", "simulations")
        ]
        
        self.entries = {}
        for i, (label, key) in enumerate(parameters, start=1):
            ttk.Label(input_frame, text=label).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.DoubleVar() if key != "simulations" else tk.IntVar()
            self.entries[key] = var
            ttk.Entry(input_frame, textvariable=var, width=15).grid(row=i, column=1, padx=5, pady=2)
        
        # Calculate button
        ttk.Button(input_frame, text="Calculate CVA", 
                  command=self.calculate_cva).grid(row=len(parameters)+1, column=0, 
                                                   columnspan=2, pady=10)
        
    def create_results_frame(self):
        """Create results display frame"""
        results_frame = ttk.LabelFrame(self.root, text="Results", padding="10")
        results_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Results text
        self.results_text = tk.Text(results_frame, width=40, height=20, 
                                   font=("Courier", 10))
        self.results_text.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, command=self.results_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_text.config(yscrollcommand=scrollbar.set)
        
    def create_plot_frame(self):
        """Create plotting frame"""
        plot_frame = ttk.LabelFrame(self.root, text="Exposure Profiles", padding="10")
        plot_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        # Configure grid weights
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
    def set_default_values(self):
        """Set default parameter values"""
        self.counterparty_var.set("ABC Corporation")
        self.entries['notional'].set(100.0)
        self.entries['fixed_rate'].set(2.5)
        self.entries['maturity'].set(5.0)
        self.entries['cp_spread'].set(150.0)
        self.entries['recovery'].set(40.0)
        self.entries['simulations'].set(1000)
        
    def calculate_cva(self):
        """Run CVA calculation"""
        try:
            # Get parameters
            notional = self.entries['notional'].get() * 1e6  # Convert to actual amount
            fixed_rate = self.entries['fixed_rate'].get() / 100
            maturity = self.entries['maturity'].get()
            cp_spread = self.entries['cp_spread'].get() / 10000  # Convert bps to decimal
            recovery = self.entries['recovery'].get() / 100
            simulations = self.entries['simulations'].get()
            
            # Create swap object and run analysis
            swap_cva = InterestRateSwapCVA(
                notional, fixed_rate, maturity, 
                cp_spread, recovery, simulations
            )
            
            results = swap_cva.run_analysis()
            
            # Display results
            self.display_results(results, swap_cva)
            self.plot_results(results)
            
        except Exception as e:
            messagebox.showerror("Error", f"Calculation error: {str(e)}")
            
    def display_results(self, results, swap_cva):
        """Display calculation results"""
        self.results_text.delete(1.0, tk.END)
        
        # Header
        self.results_text.insert(tk.END, "="*40 + "\n")
        self.results_text.insert(tk.END, "CVA CALCULATION RESULTS\n")
        self.results_text.insert(tk.END, "="*40 + "\n\n")
        
        # Counterparty info
        self.results_text.insert(tk.END, f"Counterparty: {self.counterparty_var.get()}\n")
        self.results_text.insert(tk.END, f"Calculation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Swap details
        self.results_text.insert(tk.END, "SWAP DETAILS:\n")
        self.results_text.insert(tk.END, "-"*40 + "\n")
        self.results_text.insert(tk.END, f"Notional: ${swap_cva.notional:,.0f}\n")
        self.results_text.insert(tk.END, f"Fixed Rate: {swap_cva.fixed_rate*100:.2f}%\n")
        self.results_text.insert(tk.END, f"Maturity: {swap_cva.maturity_years} years\n")
        self.results_text.insert(tk.END, f"Position: Receive Fixed, Pay Floating\n\n")
        
        # Credit parameters
        self.results_text.insert(tk.END, "CREDIT PARAMETERS:\n")
        self.results_text.insert(tk.END, "-"*40 + "\n")
        self.results_text.insert(tk.END, f"Counterparty Spread: {swap_cva.counterparty_spread*10000:.0f} bps\n")
        self.results_text.insert(tk.END, f"Recovery Rate: {swap_cva.recovery_rate*100:.0f}%\n")
        self.results_text.insert(tk.END, f"Simulations: {swap_cva.num_simulations:,}\n\n")
        
        # CVA results
        self.results_text.insert(tk.END, "CVA RESULTS:\n")
        self.results_text.insert(tk.END, "-"*40 + "\n")
        self.results_text.insert(tk.END, f"CVA: ${results['cva']:,.2f}\n")
        self.results_text.insert(tk.END, f"CVA (bps of notional): {results['cva']/swap_cva.notional*10000:.1f} bps\n\n")
        
        # Exposure statistics
        self.results_text.insert(tk.END, "EXPOSURE STATISTICS:\n")
        self.results_text.insert(tk.END, "-"*40 + "\n")
        max_epe = np.max(results['epe'])
        mean_epe = np.mean(results['epe'])
        max_ene = np.min(results['ene'])
        mean_ene = np.mean(results['ene'])
        
        self.results_text.insert(tk.END, f"Maximum EPE: ${max_epe:,.2f}\n")
        self.results_text.insert(tk.END, f"Average EPE: ${mean_epe:,.2f}\n")
        self.results_text.insert(tk.END, f"Maximum ENE: ${abs(max_ene):,.2f}\n")
        self.results_text.insert(tk.END, f"Average ENE: ${abs(mean_ene):,.2f}\n")
        
    def plot_results(self, results):
        """Plot exposure profiles"""
        # Clear previous plot
        for widget in self.root.grid_slaves(row=1, column=0):
            if isinstance(widget, ttk.LabelFrame) and widget['text'] == 'Exposure Profiles':
                for child in widget.winfo_children():
                    child.destroy()
                    
        # Get plot frame
        plot_frame = None
        for widget in self.root.grid_slaves(row=1, column=0):
            if isinstance(widget, ttk.LabelFrame) and widget['text'] == 'Exposure Profiles':
                plot_frame = widget
                break
                
        if not plot_frame:
            return
            
        # Create figure
        fig = Figure(figsize=(10, 4), dpi=100)
        
        # Plot 1: Expected Exposures
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.plot(results['time_grid'], results['epe'], 'b-', label='EPE', linewidth=2)
        ax1.plot(results['time_grid'], results['epe_95'], 'b--', label='95% EPE', alpha=0.7)
        ax1.plot(results['time_grid'], abs(results['ene']), 'r-', label='|ENE|', linewidth=2)
        ax1.plot(results['time_grid'], abs(results['ene_5']), 'r--', label='5% |ENE|', alpha=0.7)
        ax1.set_xlabel('Time (years)')
        ax1.set_ylabel('Exposure ($)')
        ax1.set_title('Expected Positive/Negative Exposure')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.ticklabel_format(style='plain', axis='y')
        
        # Plot 2: Sample paths
        ax2 = fig.add_subplot(1, 2, 2)
        # Plot first 20 swap value paths
        for i in range(min(20, results['swap_values'].shape[0])):
            ax2.plot(results['time_grid'], results['swap_values'][i, :], 
                    alpha=0.3, color='gray', linewidth=0.5)
        ax2.plot(results['time_grid'], results['epe'], 'b-', label='EPE', linewidth=2)
        ax2.plot(results['time_grid'], results['ene'], 'r-', label='ENE', linewidth=2)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.set_xlabel('Time (years)')
        ax2.set_ylabel('Swap Value ($)')
        ax2.set_title('Sample Swap Value Paths')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.ticklabel_format(style='plain', axis='y')
        
        fig.tight_layout()
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, master=plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def main():
    """Main function to run the GUI"""
    root = tk.Tk()
    app = CVACalculatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()