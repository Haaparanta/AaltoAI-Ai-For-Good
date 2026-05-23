fn main() {
    let mut total: i32 = 0;
    let mut prev: i32 = 0;

    for char in std::env::args().nth(1).unwrap_or_default().chars().rev() {
        let value = match char {
            'I' => 1,
            'V' => 5,
            'X' => 10,
            'L' => 50,
            'C' => 100,
            'D' => 500,
            'M' => 1000,
            _ => {
                eprintln!("KeyError: {char}");
                std::process::exit(1);
            }
        };

        if value < prev {
            total -= value;
        } else {
            total += value;
            prev = value;
        }
    }

    println!("{total}");
}
